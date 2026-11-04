from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from shows.models import Attendance
from shows.tests.clickthrough import ClickThroughMixin


class DetailClickThroughTests(ClickThroughMixin, TestCase):
    """Screen 5: open a show from the diary, rate it, write a review."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def setUp(self):
        self.client.login(username="demo", password="demo12345")
        self.att = Attendance.objects.get(user__username="demo", event__setlistfm_id="cba2c06a")  # unrated

    def test_diary_to_detail_rate_and_review(self):
        diary = self.client.get(reverse("shows:diary", args=["demo"]))
        detail_url = reverse("shows:detail", args=[self.att.event_id])
        self.assertContains(diary, detail_url)

        page = self.client.get(detail_url)
        self.assertAccessiblePage(page)
        self.assertLinksResolve(page)
        self.assertContains(page, "From other fans")

        rated = self.client.post(reverse("shows:rate", args=[self.att.pk]), {"rating": "3.5"}, HTTP_HX_REQUEST="true")
        self.assertAccessiblePage(rated)
        self.assertContains(rated, "Saved: 3.5 stars.")

        form = self.client.get(reverse("shows:review", args=[self.att.pk]), HTTP_HX_REQUEST="true")
        self.assertAccessiblePage(form)
        saved = self.client.post(reverse("shows:review", args=[self.att.pk]), {"review": "Brixton shook."},
                                 HTTP_HX_REQUEST="true")
        self.assertContains(saved, "Review saved.")
        self.assertContains(saved, "Edit review")

    def test_visitor_sees_reviews_and_a_sign_up_prompt(self):
        self.client.logout()
        boygenius = Attendance.objects.get(user__username="demo", event__setlistfm_id="ce93038b")
        page = self.client.get(reverse("shows:detail", args=[boygenius.event_id]))
        self.assertAccessiblePage(page)
        self.assertContains(page, "Riley Okafor")
        self.assertContains(page, "Three voices, one mic")
        self.assertContains(page, "Start your concert diary")
