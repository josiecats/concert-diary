from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from shows.models import Attendance, Event
from shows.tests.factories import PASSWORD, make_user


class US5ManualEntryTests(TestCase):
    """US-5: add a show manually when it isn't on setlist.fm."""

    def setUp(self):
        self.user = make_user("mara")
        self.client.login(username="mara", password=PASSWORD)
        self.url = reverse("shows:add_manual")
        self.valid = {
            "artist": "Salt Lick Choir", "event_date": "2024-08-30", "venue_name": "Funk 'n Waffles",
            "city": "Syracuse", "country": "United States", "tour_name": "", "rating": "", "review": "",
        }

    def test_form_requires_artist_date_venue_and_city(self):
        resp = self.client.post(self.url, {"artist": "", "event_date": "", "venue_name": "", "city": ""})
        self.assertEqual(resp.status_code, 200)
        form = resp.context["form"]
        for field in ("artist", "event_date", "venue_name", "city"):
            self.assertIn(field, form.errors)
        self.assertContains(resp, "City is needed to place the show on your map")
        self.assertFalse(Attendance.objects.exists())

    def test_manual_show_is_user_added_and_counts_in_stats_and_map(self):
        resp = self.client.post(self.url, self.valid)
        att = Attendance.objects.get(user=self.user)
        self.assertRedirects(resp, reverse("shows:detail", args=[att.event_id]), fetch_redirect_response=False)
        self.assertEqual(att.event.source, Event.SOURCE_USER)
        self.assertEqual(att.event.created_by, self.user)

        profile = self.client.get(reverse("accounts:profile", args=["mara"]))
        self.assertEqual(profile.context["stats"]["shows"], 1)
        pins = self.client.get(reverse("maps:venues", args=["mara"])).json()["pins"]
        self.assertEqual(pins[0]["name"], "Funk 'n Waffles")
        self.assertEqual(pins[0]["city"], "Syracuse")

    def test_manual_show_in_unknown_city_lands_in_not_on_the_map(self):
        self.client.post(self.url, {**self.valid, "city": "Ithaca"})
        profile = self.client.get(reverse("accounts:profile", args=["mara"]))
        self.assertEqual(len(profile.context["not_on_map"]), 1)
        self.assertEqual(profile.context["stats"]["cities"], 1)

    def test_rating_and_review_can_be_added_at_log_time(self):
        self.client.post(self.url, {**self.valid, "rating": "4.5", "review": "Sweaty and perfect."})
        att = Attendance.objects.get(user=self.user)
        self.assertEqual(str(att.rating), "4.5")
        self.assertEqual(att.review, "Sweaty and perfect.")

    def test_future_dates_are_rejected(self):
        future = (date.today() + timedelta(days=3)).isoformat()
        resp = self.client.post(self.url, {**self.valid, "event_date": future})
        self.assertIn("can't be in the future", resp.context["form"].errors["event_date"][0])
        self.assertFalse(Attendance.objects.exists())

    def test_adding_the_same_manual_show_twice_is_blocked(self):
        self.client.post(self.url, self.valid)
        resp = self.client.post(self.url, {**self.valid, "artist": "salt lick choir"})
        self.assertContains(resp, "already in your diary")
        self.assertEqual(Attendance.objects.count(), 1)

    def test_form_prefills_from_search(self):
        resp = self.client.get(self.url, {"artist": "Salt Lick Choir", "city": "Ithaca"})
        self.assertContains(resp, 'value="Salt Lick Choir"')
        self.assertContains(resp, 'value="Ithaca"')
