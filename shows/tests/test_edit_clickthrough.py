from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from shows.models import Attendance
from shows.tests.clickthrough import ClickThroughMixin


class EditDeleteClickThroughTests(ClickThroughMixin, TestCase):
    """Screen 6: diary -> edit -> save, then delete with confirmation."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def setUp(self):
        self.client.login(username="demo", password="demo12345")
        self.att = Attendance.objects.get(user__username="demo", top3_rank=1)

    def test_edit_page_is_labelled_and_saves(self):
        edit_url = reverse("shows:edit", args=[self.att.pk])
        self.assertContains(self.client.get(reverse("shows:diary", args=["demo"])), edit_url)
        page = self.client.get(edit_url)
        self.assertAccessiblePage(page)
        self.assertLinksResolve(page, skip=("/accounts/logout/", reverse("shows:delete", args=[self.att.pk])))
        resp = self.client.post(edit_url, {"rating": "4.5", "review": "Still the best night."}, follow=True)
        self.assertContains(resp, "Your changes are saved.")
        self.assertContains(resp, "Edited ")

    def test_delete_confirm_cancel_then_confirm(self):
        url = reverse("shows:delete", args=[self.att.pk])
        confirm = self.client.get(url, HTTP_HX_REQUEST="true")
        self.assertAccessiblePage(confirm)
        cancel = self.client.get(url, {"cancel": "1"}, HTTP_HX_REQUEST="true")
        self.assertContains(cancel, "Delete from diary")
        self.assertTrue(Attendance.objects.filter(pk=self.att.pk).exists())

        self.client.post(url, HTTP_HX_REQUEST="true")
        profile = self.client.get(reverse("accounts:profile", args=["demo"]))
        self.assertEqual(profile.context["stats"]["shows"], 14)
        self.assertEqual([a.top3_rank for a in profile.context["top3"]], [1, 2])
