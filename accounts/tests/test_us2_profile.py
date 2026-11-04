from datetime import date

from django.test import TestCase
from django.urls import reverse

from shows.models import Attendance
from shows.tests.factories import PASSWORD, log, make_event, make_user, make_venue


class US2PublicProfileTests(TestCase):
    """US-2: a public profile showing my stats, Top 3 and map."""

    def setUp(self):
        self.user = make_user(
            "mara", display_name="Mara Quinn", bio="Front-row optimist.", home_city="Syracuse, NY",
            avatar_url="https://example.com/mara.png",
        )
        self.url = reverse("accounts:profile", args=["mara"])

    def test_profile_shows_avatar_name_bio_city_and_joined_date(self):
        resp = self.client.get(self.url)
        self.assertContains(resp, "Mara Quinn")
        self.assertContains(resp, "Front-row optimist.")
        self.assertContains(resp, "Syracuse, NY")
        self.assertContains(resp, 'src="https://example.com/mara.png"')
        self.assertContains(resp, f"Joined {self.user.date_joined:%B %Y}")

    def test_stats_count_shows_artists_venues_and_cities_and_update_on_log_and_delete(self):
        chicago = make_venue("Metro", city="Chicago")
        philly = make_venue("Union Transfer", city="Philadelphia")
        log(self.user, make_event("Big Thief", chicago, date(2019, 11, 2)))
        log(self.user, make_event("Big Thief", philly, date(2022, 4, 12)))
        third = log(self.user, make_event("Mitski", chicago, date(2019, 3, 30)))

        resp = self.client.get(self.url)
        self.assertEqual(resp.context["stats"], {"shows": 3, "artists": 2, "venues": 2, "cities": 2})
        self.assertContains(resp, 'data-stat="shows">3<')

        third.delete()
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["stats"], {"shows": 2, "artists": 1, "venues": 2, "cities": 2})

    def test_logged_out_visitor_can_view_public_profile(self):
        self.client.logout()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Mara Quinn")

    def test_private_profile_is_hidden_from_visitors_but_not_owner(self):
        self.user.profile.is_private = True
        self.user.profile.save()

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "This profile is private", status_code=403)
        self.assertNotContains(resp, "Front-row optimist.", status_code=403)

        make_user("riley")
        self.client.login(username="riley", password=PASSWORD)
        self.assertEqual(self.client.get(self.url).status_code, 403)

        self.client.login(username="mara", password=PASSWORD)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Only you can see this profile")

    def test_owner_can_set_profile_private_in_settings(self):
        self.client.login(username="mara", password=PASSWORD)
        resp = self.client.post(reverse("accounts:settings"), {
            "display_name": "Mara Quinn", "bio": "", "home_city": "Syracuse, NY", "avatar_url": "", "is_private": "on",
        })
        self.assertRedirects(resp, self.url)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.is_private)

    def test_unknown_username_is_404(self):
        self.assertEqual(self.client.get(reverse("accounts:profile", args=["nobody"])).status_code, 404)

    def test_private_profile_hides_its_diary_and_map_data(self):
        self.user.profile.is_private = True
        self.user.profile.save()
        log(self.user)
        self.assertEqual(self.client.get(reverse("shows:diary", args=["mara"])).status_code, 403)
        self.assertEqual(self.client.get(reverse("maps:venues", args=["mara"])).status_code, 403)
        self.assertEqual(Attendance.objects.count(), 1)
