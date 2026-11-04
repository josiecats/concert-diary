from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from shows.models import Event
from shows.tests.factories import PASSWORD, log, make_event, make_user


class US6DiaryTests(TestCase):
    """US-6: see my diary as a list sorted by date."""

    def setUp(self):
        self.user = make_user("mara")
        self.old = log(self.user, make_event("Radiohead", event_date=date(2016, 5, 20)), rating=Decimal("5.0"))
        self.mid = log(self.user, make_event("Mitski", event_date=date(2019, 3, 30)), rating=None,
                       review="Quiet crowd, loud heart. " * 20)
        self.new = log(self.user, make_event("Wednesday", event_date=date(2023, 9, 22)), rating=Decimal("3.5"),
                       review="Guitar tone could strip paint.")
        self.url = reverse("shows:diary", args=["mara"])

    def entries(self, **params):
        resp = self.client.get(self.url, params)
        self.assertEqual(resp.status_code, 200)
        return resp, [a.event.artist.name for a in resp.context["entries"]]

    def test_lists_every_logged_show_newest_first_with_rating_and_review_snippet(self):
        resp, names = self.entries()
        self.assertEqual(names, ["Wednesday", "Mitski", "Radiohead"])
        self.assertContains(resp, 'aria-label="3.5 out of 5 stars"')
        self.assertContains(resp, "Guitar tone could strip paint.")
        self.assertContains(resp, "Quiet crowd, loud heart.")
        self.assertNotContains(resp, "Quiet crowd, loud heart. " * 20)  # long reviews are truncated

    def test_can_sort_by_date_or_rating(self):
        _, oldest = self.entries(sort="oldest")
        self.assertEqual(oldest, ["Radiohead", "Mitski", "Wednesday"])
        _, by_rating = self.entries(sort="rating")
        self.assertEqual(by_rating, ["Radiohead", "Wednesday", "Mitski"])  # unrated last

    def test_can_filter_by_year(self):
        resp, names = self.entries(year="2019")
        self.assertEqual(names, ["Mitski"])
        self.assertEqual(resp.context["years"], [2023, 2019, 2016])
        _, none = self.entries(year="2001")
        self.assertEqual(none, [])

    def test_htmx_filter_returns_partial_and_pushes_url(self):
        resp = self.client.get(self.url, {"sort": "rating"}, HTTP_HX_REQUEST="true")
        self.assertNotContains(resp, "<html")
        self.assertContains(resp, 'id="diary-list"')
        page = self.client.get(self.url)
        self.assertContains(page, 'hx-push-url="true"')
        self.assertContains(page, '<label for="diary-sort"')
        self.assertContains(page, '<label for="diary-year"')

    def test_bad_params_fall_back_to_defaults(self):
        _, names = self.entries(sort="nonsense", year="abc")
        self.assertEqual(names, ["Wednesday", "Mitski", "Radiohead"])

    def test_user_added_shows_are_marked(self):
        log(self.user, make_event("Salt Lick Choir", event_date=date(2024, 8, 30), source=Event.SOURCE_USER))
        resp, _ = self.entries()
        self.assertContains(resp, "User-added")

    def test_hidden_review_shows_to_author_but_not_visitors(self):
        self.new.review_hidden = True
        self.new.save()
        resp, _ = self.entries()
        self.assertNotContains(resp, "Guitar tone could strip paint.")
        self.client.login(username="mara", password=PASSWORD)
        resp, _ = self.entries()
        self.assertContains(resp, "Guitar tone could strip paint.")
        self.assertContains(resp, "Hidden from others by a moderator")

    def test_empty_diary_invites_owner_to_log(self):
        make_user("newbie")
        self.client.login(username="newbie", password=PASSWORD)
        resp = self.client.get(reverse("shows:diary", args=["newbie"]))
        self.assertContains(resp, "Log your first show")
