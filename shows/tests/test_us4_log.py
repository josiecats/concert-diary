import json

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from shows.models import Attendance, Event
from shows.tests.factories import PASSWORD, make_user

BOYGENIUS_MSG = "ce93038b"  # boygenius, Madison Square Garden, 2023-08-04 (fixture)


class US4LogShowTests(TestCase):
    """US-4: log a show in one tap from search results."""

    def setUp(self):
        cache.clear()
        self.user = make_user("mara")
        self.client.login(username="mara", password=PASSWORD)
        self.url = reverse("shows:log", args=[BOYGENIUS_MSG])

    def test_log_adds_show_and_returns_confirmation(self):
        resp = self.client.post(self.url, HTTP_HX_REQUEST="true")
        self.assertContains(resp, "In your diary")
        self.assertNotContains(resp, "<html")
        self.assertTrue(Attendance.objects.filter(user=self.user, event__setlistfm_id=BOYGENIUS_MSG).exists())

    def test_logging_same_event_twice_is_blocked(self):
        self.client.post(self.url)
        resp = self.client.post(self.url, HTTP_HX_REQUEST="true")
        self.assertContains(resp, "already in your diary", status_code=409)
        self.assertEqual(Attendance.objects.filter(user=self.user).count(), 1)

    def test_venue_pin_appears_without_page_reload(self):
        resp = self.client.post(self.url, HTTP_HX_REQUEST="true")
        trigger = json.loads(resp["HX-Trigger"])
        self.assertEqual(trigger["show-logged"]["venue"], "Madison Square Garden")
        pins = self.client.get(reverse("maps:venues", args=["mara"])).json()["pins"]
        self.assertEqual([p["name"] for p in pins], ["Madison Square Garden"])
        # The search page carries a live mini-map that listens for that event.
        page = self.client.get(reverse("shows:search"))
        self.assertContains(page, "data-diary-map")
        self.assertContains(page, reverse("maps:venues", args=["mara"]))

    def test_results_mark_shows_already_in_diary(self):
        self.client.post(self.url)
        resp = self.client.get(reverse("shows:search_results"), {"artist": "boygenius"}, HTTP_HX_REQUEST="true")
        self.assertContains(resp, "In your diary", count=1)
        self.assertContains(resp, 'aria-label="Log boygenius at Hollywood Bowl on Oct 21, 2023"')

    def test_first_log_caches_event_and_later_logs_reuse_it(self):
        self.client.post(self.url)
        make_user("riley")
        self.client.login(username="riley", password=PASSWORD)
        self.client.post(self.url)
        self.assertEqual(Event.objects.filter(setlistfm_id=BOYGENIUS_MSG).count(), 1)
        self.assertEqual(Attendance.objects.count(), 2)

    def test_unknown_setlist_is_404(self):
        self.assertEqual(self.client.post(reverse("shows:log", args=["nope1234"])).status_code, 404)

    def test_log_requires_post_and_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.client.logout()
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.assertFalse(Attendance.objects.exists())
