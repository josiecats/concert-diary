from datetime import date

from django.test import TestCase
from django.urls import reverse

from shows.models import Event
from shows.tests.factories import PASSWORD, log, make_event, make_user, make_venue


class US10MapTests(TestCase):
    """US-10: a map with a pin for every venue I've been to."""

    def setUp(self):
        self.user = make_user("mara")
        self.metro = make_venue("Metro", city="Chicago", lat=41.9496, lng=-87.6589)
        self.bowl = make_venue("Hollywood Bowl", city="Los Angeles", lat=34.1122, lng=-118.3391)
        log(self.user, make_event("Big Thief", self.metro, date(2019, 11, 2)))
        log(self.user, make_event("Mitski", self.metro, date(2019, 3, 30)))
        log(self.user, make_event("Phoebe Bridgers", self.bowl, date(2022, 6, 18)))
        self.basement = make_venue("Cayuga Street Basement", city="Ithaca", lat=None, lng=None, created_by=self.user)
        self.unmapped = log(self.user, make_event("Salt Lick Choir", self.basement, date(2024, 8, 30), source=Event.SOURCE_USER))
        self.json_url = reverse("maps:venues", args=["mara"])

    def pins(self):
        return {p["name"]: p for p in self.client.get(self.json_url).json()["pins"]}

    def test_one_pin_per_venue_with_visit_count(self):
        pins = self.pins()
        self.assertEqual(set(pins), {"Metro", "Hollywood Bowl"})
        self.assertEqual(pins["Metro"]["count"], 2)
        self.assertEqual(pins["Hollywood Bowl"]["count"], 1)

    def test_pin_lists_shows_with_date_and_artist(self):
        shows = self.pins()["Metro"]["shows"]
        self.assertEqual([s["artist"] for s in shows], ["Big Thief", "Mitski"])
        self.assertEqual(shows[0]["date"], "Nov 2, 2019")
        self.assertTrue(shows[0]["url"].startswith("/shows/"))

    def test_map_fits_all_pins(self):
        data = self.client.get(self.json_url).json()
        self.assertEqual(data["bounds"], [[34.1122, -118.3391], [41.9496, -87.6589]])
        html = self.client.get(reverse("accounts:profile", args=["mara"])).content.decode()
        self.assertIn(f'data-url="{self.json_url}"', html)
        self.assertIn("diary-map.js", html)

    def test_shows_without_coordinates_are_listed_under_not_on_the_map(self):
        resp = self.client.get(reverse("accounts:profile", args=["mara"]))
        self.assertContains(resp, "Not on the map")
        self.assertContains(resp, "Salt Lick Choir")
        self.assertContains(resp, "Cayuga Street Basement")
        self.assertNotContains(resp, "Fix location")  # visitors can't fix it

        self.client.login(username="mara", password=PASSWORD)
        resp = self.client.get(reverse("accounts:profile", args=["mara"]))
        self.assertContains(resp, reverse("maps:fix_location", args=[self.basement.pk]))

    def test_fix_location_by_coordinates_puts_the_venue_on_the_map(self):
        self.client.login(username="mara", password=PASSWORD)
        resp = self.client.post(
            reverse("maps:fix_location", args=[self.basement.pk]),
            {"city": "Ithaca", "lat": "42.4406", "lng": "-76.4966"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["HX-Trigger"], "map-changed")
        self.assertIn("Cayuga Street Basement", self.pins())

    def test_fix_location_by_known_city_uses_geocoder(self):
        self.client.login(username="mara", password=PASSWORD)
        self.client.post(reverse("maps:fix_location", args=[self.basement.pk]), {"city": "Syracuse", "lat": "", "lng": ""})
        self.basement.refresh_from_db()
        self.assertEqual(self.basement.city, "Syracuse")
        self.assertIsNotNone(self.basement.lat)

    def test_fix_location_with_unknown_city_and_no_coordinates_explains_what_to_do(self):
        self.client.login(username="mara", password=PASSWORD)
        resp = self.client.post(
            reverse("maps:fix_location", args=[self.basement.pk]), {"city": "Nowhereville", "lat": "", "lng": ""},
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(resp, "enter coordinates", status_code=422)

    def test_only_the_venue_creator_can_fix_its_location(self):
        make_user("riley")
        self.client.login(username="riley", password=PASSWORD)
        resp = self.client.post(reverse("maps:fix_location", args=[self.basement.pk]), {"city": "Syracuse"})
        self.assertEqual(resp.status_code, 404)
