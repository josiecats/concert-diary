from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from shows.tests.clickthrough import ClickThroughMixin


class DiaryClickThroughTests(ClickThroughMixin, TestCase):
    """Screen 4: browse, sort and filter the seeded demo diary."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_visitor_and_owner_can_click_through_the_diary(self):
        url = reverse("shows:diary", args=["demo"])
        resp = self.client.get(url)
        self.assertEqual(len(resp.context["entries"]), 15)
        self.assertAccessiblePage(resp)
        self.assertLinksResolve(resp)
        self.assertNotContains(resp, ">Edit<")

        self.client.login(username="demo", password="demo12345")
        resp = self.client.get(url)
        self.assertAccessiblePage(resp)
        self.assertContains(resp, ">Edit<")

        for params in ({"sort": "rating"}, {"sort": "oldest", "year": "2023"}):
            partial = self.client.get(url, params, HTTP_HX_REQUEST="true")
            self.assertAccessiblePage(partial)
            self.assertNotContains(partial, "<html")
        top = self.client.get(url, {"sort": "rating"}).context["entries"][0]
        self.assertEqual(str(top.rating), "5.0")
