from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from shows.models import Attendance
from shows.tests.clickthrough import ClickThroughMixin


class SearchClickThroughTests(ClickThroughMixin, TestCase):
    """Screen 3: search, log in one tap, then add a show manually, as the demo user."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def setUp(self):
        cache.clear()
        self.client.login(username="demo", password="demo12345")

    def test_search_page_is_labelled_and_links_resolve(self):
        resp = self.client.get(reverse("shows:search"))
        self.assertAccessiblePage(resp)
        self.assertLinksResolve(resp)

    def test_search_then_log_then_see_it_marked(self):
        before = Attendance.objects.filter(user__username="demo").count()
        results = self.client.get(reverse("shows:search_results"), {"artist": "mitski"}, HTTP_HX_REQUEST="true")
        self.assertAccessiblePage(results)
        unlogged = [r for r in results.context["results"] if r.id not in results.context["logged_ids"]]
        self.assertEqual(len(unlogged), 2)  # demo already logged Mitski at Metro

        resp = self.client.post(reverse("shows:log", args=[unlogged[0].id]), HTTP_HX_REQUEST="true")
        self.assertContains(resp, "In your diary")
        self.assertIn("show-logged", resp["HX-Trigger"])
        self.assertEqual(Attendance.objects.filter(user__username="demo").count(), before + 1)

        again = self.client.get(reverse("shows:search_results"), {"artist": "mitski"}, HTTP_HX_REQUEST="true")
        self.assertEqual(len(again.context["logged_ids"]), 2)

    def test_no_match_leads_to_prefilled_manual_form(self):
        results = self.client.get(reverse("shows:search_results"), {"artist": "Basement Ghosts", "city": "Ithaca"},
                                  HTTP_HX_REQUEST="true")
        form = self.client.get(results.context["manual_url"])
        self.assertAccessiblePage(form)
        self.assertContains(form, 'value="Basement Ghosts"')
        self.assertContains(form, 'value="Ithaca"')
