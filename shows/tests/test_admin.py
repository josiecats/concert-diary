"""Every model is registered in Django admin, and the moderation tools work (US-11)."""

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from shows.models import Artist, Attendance, Event, Report, Tag, Venue
from shows.tests.factories import log, make_user

User = get_user_model()


class AdminRegistrationTests(TestCase):
    MODELS = [Profile, Artist, Venue, Event, Attendance, Tag, Report]

    def setUp(self):
        self.staff = User.objects.create_superuser("mod", "mod@example.com", "mod-pass-123")
        self.client.force_login(self.staff)
        self.att = log(make_user("mara"), review="Loud and great")
        Report.objects.create(attendance=self.att, reporter=self.staff, reason="Check")

    def test_every_model_is_registered(self):
        for model in self.MODELS:
            with self.subTest(model=model.__name__):
                self.assertTrue(admin.site.is_registered(model))

    def test_changelist_and_add_pages_load(self):
        for model in self.MODELS:
            opts = model._meta
            for view in ("changelist", "add"):
                with self.subTest(model=opts.model_name, view=view):
                    resp = self.client.get(reverse(f"admin:{opts.app_label}_{opts.model_name}_{view}"))
                    self.assertEqual(resp.status_code, 200)

    def test_tag_filter_splits_premade_and_custom(self):
        Tag.objects.create(name="Rain all night", owner=self.att.user)
        url = reverse("admin:shows_tag_changelist")
        self.assertContains(self.client.get(url, {"type": "custom"}), "Rain all night")
        self.assertNotContains(self.client.get(url, {"type": "premade"}), "Rain all night")

    def test_admin_rejects_another_users_custom_tag_with_a_form_error(self):
        theirs = Tag.objects.create(name="Front row", owner=make_user("jo"))
        url = reverse("admin:shows_attendance_change", args=[self.att.pk])
        resp = self.client.post(url, {
            "user": self.att.user.pk, "event": self.att.event.pk, "rating": "", "review": self.att.review,
            "tags": [theirs.pk], "top3_rank": "",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "another user&#x27;s custom tags: Front row")
        self.assertFalse(self.att.tags.exists())

    def test_hide_review_action_hides_review_and_closes_report_us11(self):
        resp = self.client.post(reverse("admin:shows_report_changelist"), {
            "action": "hide_review", "_selected_action": list(Report.objects.values_list("pk", flat=True)),
        })
        self.assertEqual(resp.status_code, 302)
        self.att.refresh_from_db()
        self.assertTrue(self.att.review_hidden)
        self.assertEqual(Report.objects.get().status, Report.STATUS_HIDDEN)
