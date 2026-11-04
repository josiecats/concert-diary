import time
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from services.setlistfm import MockSetlistClient
from shows.tests.factories import PASSWORD, make_user


class US3SearchTests(TestCase):
    """US-3: search for a past show by artist and narrow by date, venue or city."""

    def setUp(self):
        cache.clear()
        make_user("mara")
        self.client.login(username="mara", password=PASSWORD)
        self.url = reverse("shows:search_results")

    def results(self, **params):
        resp = self.client.get(self.url, params, HTTP_HX_REQUEST="true")
        self.assertEqual(resp.status_code, 200)
        return resp, resp.context["results"]

    def test_typing_artist_name_returns_matching_events_newest_first(self):
        resp, results = self.results(artist="japanese brea")
        self.assertEqual([r.artist_name for r in results], ["Japanese Breakfast"] * 3)
        dates = [r.event_date for r in results]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertContains(resp, "3 shows found")

    def test_search_input_is_debounced_and_labelled(self):
        resp = self.client.get(reverse("shows:search"))
        self.assertContains(resp, 'hx-trigger="input delay:300ms')
        self.assertContains(resp, '<label for="id_artist"')

    def test_year_venue_and_city_filters_narrow_results(self):
        _, all_mitski = self.results(artist="Mitski")
        self.assertEqual(len(all_mitski), 3)
        _, by_year = self.results(artist="Mitski", year="2022")
        self.assertEqual([r.venue_name for r in by_year], ["Stubb's BBQ"])
        _, by_venue = self.results(artist="Mitski", venue="metro")
        self.assertEqual([r.city for r in by_venue], ["Chicago"])
        _, by_city = self.results(artist="Mitski", city="London")
        self.assertEqual([r.venue_name for r in by_city], ["Royal Albert Hall"])
        _, none = self.results(artist="Mitski", city="Tokyo")
        self.assertEqual(none, [])

    def test_each_result_shows_artist_date_venue_and_city(self):
        resp, _ = self.results(artist="Wednesday")
        self.assertContains(resp, "Wednesday")
        self.assertContains(resp, "Sep 22, 2023")
        self.assertContains(resp, "The Westcott Theater")
        self.assertContains(resp, "Syracuse")

    def test_cached_artist_results_load_in_under_two_seconds_without_refetching(self):
        with mock.patch.object(MockSetlistClient, "search", wraps=MockSetlistClient().search) as spy:
            self.results(artist="Big Thief")
            start = time.perf_counter()
            self.results(artist="Big Thief")
            elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 2.0)
        self.assertEqual(spy.call_count, 1)

    def test_short_query_prompts_instead_of_searching(self):
        resp, results = self.results(artist="b")
        self.assertEqual(results, [])
        self.assertContains(resp, "Type at least 2 letters")

    def test_no_results_offers_manual_entry(self):
        resp, _ = self.results(artist="Salt Lick Choir")
        self.assertContains(resp, "No shows match")
        self.assertContains(resp, reverse("shows:add_manual") + "?artist=Salt+Lick+Choir")

    def test_full_page_search_works_without_htmx(self):
        resp = self.client.get(reverse("shows:search"), {"artist": "Radiohead"})
        self.assertContains(resp, "Madison Square Garden")
        self.assertContains(resp, "<html")

    def test_search_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("shows:search")).status_code, 302)
