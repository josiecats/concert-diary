"""Model-level rules for Artist, Venue, Event, Attendance, Tag and Report.

Story-level behaviour (views, HTMX) lives in the test_usN_*.py files.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from shows.models import (
    PREMADE_TAGS,
    REVIEW_MAX_LENGTH,
    TAG_MAX_LENGTH,
    Artist,
    Attendance,
    Event,
    Report,
    Tag,
    Venue,
)
from shows.tests.factories import log, make_event, make_user, make_venue


class ArtistVenueEventModelTests(TestCase):
    def test_artist_mbid_is_unique_but_optional(self):
        Artist.objects.create(name="No MBID one")
        Artist.objects.create(name="No MBID two")  # several nulls are fine
        Artist.objects.create(name="Phish", mbid="e01646f2-2a04-450d-8bf2-0d993082e058")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Artist.objects.create(name="Phish again", mbid="e01646f2-2a04-450d-8bf2-0d993082e058")

    def test_venue_setlistfm_id_is_unique(self):
        make_venue(setlistfm_id="6bd6ca6e")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_venue(setlistfm_id="6bd6ca6e")

    def test_venue_has_coords_needs_both_lat_and_lng(self):
        self.assertTrue(make_venue(lat=41.9, lng=-87.6).has_coords)
        self.assertFalse(make_venue(lat=None, lng=None).has_coords)
        self.assertFalse(make_venue(lat=41.9, lng=None).has_coords)

    def test_event_source_defaults_to_setlistfm(self):
        artist = Artist.objects.create(name="Big Thief")
        event = Event.objects.create(artist=artist, venue=make_venue(), event_date="2022-04-12")
        self.assertEqual(event.source, Event.SOURCE_SETLISTFM)
        self.assertFalse(event.is_user_added)

    def test_user_added_event_is_flagged_us5(self):
        event = make_event(source=Event.SOURCE_USER)
        self.assertTrue(event.is_user_added)
        self.assertIsNone(event.setlistfm_id)

    def test_event_setlistfm_id_is_unique(self):
        make_event(setlistfm_id="63de4613")
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_event(setlistfm_id="63de4613")

    def test_artist_and_venue_with_events_cannot_be_deleted(self):
        event = make_event()
        with self.assertRaises(ProtectedError):
            event.artist.delete()
        with self.assertRaises(ProtectedError):
            event.venue.delete()

    def test_str(self):
        event = make_event("Big Thief", make_venue("Union Transfer", city="Philadelphia"), "2022-04-12")
        event.refresh_from_db()
        self.assertEqual(str(event.venue), "Union Transfer, Philadelphia")
        self.assertEqual(str(event), "Big Thief at Union Transfer, Philadelphia on Apr 12, 2022")


class AttendanceModelTests(TestCase):
    def setUp(self):
        self.user = make_user("mara")
        self.event = make_event()

    def att(self, **kw):
        return Attendance(user=self.user, event=self.event, **kw)

    # Ownership

    def test_every_attendance_belongs_to_a_user(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Attendance.objects.create(user=None, event=self.event)
        with self.assertRaises(ValidationError) as ctx:
            Attendance(event=self.event).full_clean()
        self.assertIn("user", ctx.exception.message_dict)

    def test_deleting_a_user_deletes_their_attendances(self):
        log(self.user, self.event)
        self.user.delete()
        self.assertFalse(Attendance.objects.exists())
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())  # the shared event stays

    def test_deleting_an_event_deletes_its_attendances(self):
        log(self.user, self.event)
        self.event.delete()
        self.assertFalse(Attendance.objects.exists())

    # US-4: one log per user per event

    def test_same_user_cannot_log_the_same_event_twice_us4(self):
        log(self.user, self.event)
        with self.assertRaises(IntegrityError), transaction.atomic():
            log(self.user, self.event)

    def test_different_users_can_log_the_same_event(self):
        log(self.user, self.event)
        log(make_user("jo"), self.event)
        self.assertEqual(self.event.attendances.count(), 2)

    # US-7: rating

    def test_rating_is_optional_us7(self):
        self.att(rating=None).full_clean()

    def test_rating_accepts_every_half_star_from_half_to_five_us7(self):
        for tenths in range(5, 51, 5):
            self.att(rating=Decimal(tenths) / 10).full_clean()

    def test_rating_rejects_values_off_the_half_star_scale_us7(self):
        for bad in ("0", "0.0", "0.3", "1.2", "4.9", "5.5", "-0.5"):
            with self.subTest(rating=bad), self.assertRaises(ValidationError) as ctx:
                self.att(rating=Decimal(bad)).full_clean()
            self.assertIn("rating", ctx.exception.message_dict)

    # US-7: review and spoiler flag

    def test_review_is_optional_and_up_to_5000_characters_us7(self):
        self.att(review="").full_clean()
        self.att(review="x" * REVIEW_MAX_LENGTH).full_clean()
        with self.assertRaises(ValidationError) as ctx:
            self.att(review="x" * (REVIEW_MAX_LENGTH + 1)).full_clean()
        self.assertIn("review", ctx.exception.message_dict)

    def test_spoiler_flag_defaults_off_and_can_be_set_us7(self):
        self.assertFalse(log(self.user, self.event).review_has_spoilers)
        flagged = log(self.user, make_event(), review="They closed with Not.", review_has_spoilers=True)
        flagged.refresh_from_db()
        self.assertTrue(flagged.review_has_spoilers)

    # US-9: Top 3

    def test_top3_rank_is_optional_and_1_to_3_us9(self):
        for rank in (None, 1, 2, 3):
            self.att(top3_rank=rank).full_clean()
        for bad in (0, 4):
            with self.subTest(rank=bad), self.assertRaises(IntegrityError), transaction.atomic():
                log(self.user, make_event(), top3_rank=bad)

    def test_top3_rank_is_unique_per_user_us9(self):
        log(self.user, make_event(), top3_rank=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            log(self.user, make_event(), top3_rank=1)
        log(make_user("jo"), make_event(), top3_rank=1)  # another user's #1 is fine

    def test_many_unranked_shows_are_allowed_us9(self):
        for _ in range(4):
            log(self.user, make_event(), top3_rank=None)
        self.assertEqual(self.user.attendances.count(), 4)

    # US-11: hidden reviews

    def test_hidden_reviews_are_visible_to_their_author_only_us11(self):
        jo = make_user("jo")
        hidden = log(self.user, self.event, review="Hidden take", review_hidden=True)
        shown = log(jo, self.event, review="Public take")
        log(jo, make_event(), review="")  # no review at all is never listed

        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(list(Attendance.objects.visible_reviews_for(AnonymousUser())), [shown])
        self.assertEqual(list(Attendance.objects.visible_reviews_for(jo)), [shown])
        self.assertCountEqual(Attendance.objects.visible_reviews_for(self.user), [hidden, shown])

    def test_timestamps(self):
        att = log(self.user, self.event)
        self.assertIsNotNone(att.created_at)
        first_update = att.updated_at
        att.rating = Decimal("4.5")
        att.save()
        self.assertGreater(att.updated_at, first_update)


class TagModelTests(TestCase):
    def setUp(self):
        self.mara = make_user("mara")
        self.jo = make_user("jo")

    def test_premade_tags_from_the_design_are_seeded(self):
        self.assertCountEqual(Tag.objects.premade().values_list("name", flat=True), PREMADE_TAGS)
        self.assertEqual(len(PREMADE_TAGS), 8)
        self.assertTrue(all(t.is_premade for t in Tag.objects.premade()))

    def test_premade_tag_names_are_unique_ignoring_case(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Tag.objects.create(name="great SOUND")

    def test_custom_tag_names_are_unique_per_user_ignoring_case(self):
        Tag.objects.create(name="Openers ruled", owner=self.mara)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Tag.objects.create(name="openers RULED", owner=self.mara)
        Tag.objects.create(name="Openers ruled", owner=self.jo)  # someone else can have the same tag
        self.assertEqual(Tag.objects.filter(name__iexact="openers ruled").count(), 2)

    def test_custom_tag_cannot_duplicate_a_premade_tag(self):
        with self.assertRaises(ValidationError) as ctx:
            Tag(name="  wild crowd ", owner=self.mara).full_clean()
        self.assertIn("name", ctx.exception.message_dict)

    def test_tag_name_is_required_and_at_most_24_characters(self):
        Tag(name="x" * TAG_MAX_LENGTH, owner=self.mara).full_clean()
        for bad in ("", "   ", "x" * (TAG_MAX_LENGTH + 1)):
            with self.subTest(name=bad), self.assertRaises(ValidationError):
                Tag(name=bad, owner=self.mara).full_clean()

    def test_clean_strips_whitespace(self):
        tag = Tag(name="  Rain all night  ", owner=self.mara)
        tag.full_clean()
        self.assertEqual(tag.name, "Rain all night")

    def test_str_marks_custom_tags_with_a_hash(self):
        self.assertEqual(str(Tag.objects.get(name="Great sound")), "Great sound")
        self.assertEqual(str(Tag.objects.create(name="Rain all night", owner=self.mara)), "# Rain all night")

    def test_available_to_is_premade_plus_own_custom_tags(self):
        mine = Tag.objects.create(name="Rain all night", owner=self.mara)
        theirs = Tag.objects.create(name="Front row", owner=self.jo)
        available = Tag.objects.available_to(self.mara)
        self.assertIn(mine, available)
        self.assertNotIn(theirs, available)
        self.assertEqual(available.count(), len(PREMADE_TAGS) + 1)

        from django.contrib.auth.models import AnonymousUser

        self.assertEqual(Tag.objects.available_to(AnonymousUser()).count(), len(PREMADE_TAGS))

    def test_attendance_can_use_premade_and_own_custom_tags(self):
        att = log(self.mara)
        mine = Tag.objects.create(name="Rain all night", owner=self.mara)
        premade = Tag.objects.get(name="With friends")
        att.tags.add(premade, mine)
        self.assertCountEqual(att.tags.all(), [premade, mine])
        self.assertIn(att, premade.attendances.all())

    def test_attendance_cannot_use_another_users_custom_tag(self):
        att = log(self.mara)
        theirs = Tag.objects.create(name="Front row", owner=self.jo)
        # The check raises inside Django's m2m transaction, so each attempt gets its own savepoint.
        with self.assertRaises(ValidationError), transaction.atomic():
            att.tags.add(theirs)
        with self.assertRaises(ValidationError), transaction.atomic():
            att.tags.set([theirs])
        with self.assertRaises(ValidationError), transaction.atomic():
            theirs.attendances.add(att)  # the reverse side is checked too
        self.assertFalse(att.tags.exists())

    def test_deleting_a_user_deletes_their_custom_tags_only(self):
        Tag.objects.create(name="Rain all night", owner=self.mara)
        jo_tag = Tag.objects.create(name="Front row", owner=self.jo)
        self.mara.delete()
        self.assertEqual(Tag.objects.premade().count(), len(PREMADE_TAGS))
        self.assertCountEqual(Tag.objects.filter(owner__isnull=False), [jo_tag])

    def test_deleting_a_custom_tag_removes_it_from_attendances(self):
        att = log(self.mara)
        tag = Tag.objects.create(name="Rain all night", owner=self.mara)
        att.tags.add(tag, Tag.objects.get(name="Great sound"))
        tag.delete()
        self.assertEqual(list(att.tags.values_list("name", flat=True)), ["Great sound"])

    def test_deleting_an_attendance_keeps_the_tags(self):
        att = log(self.mara)
        tag = Tag.objects.create(name="Rain all night", owner=self.mara)
        att.tags.add(tag)
        att.delete()
        self.assertTrue(Tag.objects.filter(pk=tag.pk).exists())


class ReportModelTests(TestCase):
    def setUp(self):
        self.author = make_user("mara")
        self.reporter = make_user("jo")
        self.att = log(self.author, review="Something rude")

    def report(self, **kw):
        return Report.objects.create(attendance=self.att, reporter=self.reporter, reason="Abusive", **kw)

    def test_report_status_defaults_to_open_us11(self):
        self.assertEqual(self.report().status, Report.STATUS_OPEN)

    def test_report_status_must_be_a_known_choice_us11(self):
        with self.assertRaises(ValidationError):
            Report(attendance=self.att, reporter=self.reporter, reason="x", status="bogus").full_clean()

    def test_report_reason_is_required_and_capped_us11(self):
        for bad in ("", "x" * 501):
            with self.subTest(length=len(bad)), self.assertRaises(ValidationError):
                Report(attendance=self.att, reporter=self.reporter, reason=bad).full_clean()

    def test_reports_go_when_the_attendance_or_reporter_goes_us11(self):
        self.report()
        self.reporter.delete()
        self.assertFalse(Report.objects.exists())
        Report.objects.create(attendance=self.att, reporter=make_user("sam"), reason="Spam")
        self.att.delete()
        self.assertFalse(Report.objects.exists())
