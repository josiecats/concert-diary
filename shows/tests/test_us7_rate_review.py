from datetime import date

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from shows.models import Attendance
from shows.tests.factories import PASSWORD, log, make_event, make_user, make_venue


class US7RateAndReviewTests(TestCase):
    """US-7: rate a show from 0.5 to 5 stars and write a review."""

    def setUp(self):
        self.user = make_user("mara")
        self.client.login(username="mara", password=PASSWORD)
        self.event = make_event("Big Thief", make_venue("Union Transfer", city="Philadelphia"), date(2022, 4, 12))
        self.att = log(self.user, self.event)
        self.rate_url = reverse("shows:rate", args=[self.att.pk])
        self.review_url = reverse("shows:review", args=[self.att.pk])

    def rate(self, value):
        return self.client.post(self.rate_url, {"rating": value}, HTTP_HX_REQUEST="true")

    def test_rating_uses_half_star_steps_from_half_to_five(self):
        for value in ("0.5", "3.5", "5.0"):
            resp = self.rate(value)
            self.assertEqual(resp.status_code, 200, value)
            self.att.refresh_from_db()
            self.assertEqual(str(self.att.rating), value)
        for bad in ("0", "0.0", "3.3", "5.5", "-1", "abc"):
            self.assertEqual(self.rate(bad).status_code, 422, bad)
        self.att.refresh_from_db()
        self.assertEqual(str(self.att.rating), "5.0")

    def test_rating_is_optional_and_can_be_cleared(self):
        self.rate("4.0")
        resp = self.rate("")
        self.assertEqual(resp.status_code, 200)
        self.att.refresh_from_db()
        self.assertIsNone(self.att.rating)

    def test_star_widget_offers_ten_labelled_half_steps_plus_no_rating(self):
        resp = self.client.get(reverse("shows:detail", args=[self.event.pk]))
        html = resp.content.decode()
        self.assertEqual(html.count('name="rating" type="radio"'), 11)
        self.assertContains(resp, "0.5 stars")
        self.assertContains(resp, "4.5 stars")
        self.assertContains(resp, "No rating")
        self.assertContains(resp, "<legend")

    def test_review_is_optional_and_up_to_5000_characters(self):
        resp = self.client.post(self.review_url, {"review": "x" * 5000}, HTTP_HX_REQUEST="true")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(self.review_url, {"review": "x" * 5001}, HTTP_HX_REQUEST="true")
        self.assertContains(resp, "5,000 characters", status_code=422)
        self.att.refresh_from_db()
        self.assertEqual(len(self.att.review), 5000)
        resp = self.client.post(self.review_url, {"review": ""}, HTTP_HX_REQUEST="true")
        self.assertEqual(resp.status_code, 200)

    def test_rating_and_review_can_be_added_at_log_time_or_later(self):
        cache.clear()
        resp = self.client.post(reverse("shows:log", args=["5695b153"]), HTTP_HX_REQUEST="true")  # Sharon Van Etten
        later = Attendance.objects.get(user=self.user, event__setlistfm_id="5695b153")
        self.assertContains(resp, reverse("shows:detail", args=[later.event_id]))
        self.assertContains(resp, "Rate and review")
        self.client.post(reverse("shows:rate", args=[later.pk]), {"rating": "4.5"})
        self.client.post(reverse("shows:review", args=[later.pk]), {"review": "Seventeen Seconds of silence."})
        later.refresh_from_db()
        self.assertEqual((str(later.rating), later.review), ("4.5", "Seventeen Seconds of silence."))

    def test_review_shows_on_diary_entry_and_on_show_detail_page(self):
        self.client.post(self.review_url, {"review": "Adrianne played Simulation Swarm alone."})
        self.client.logout()
        self.assertContains(self.client.get(reverse("shows:diary", args=["mara"])), "Simulation Swarm alone")
        detail = self.client.get(reverse("shows:detail", args=[self.event.pk]))
        self.assertContains(detail, "Simulation Swarm alone")
        self.assertContains(detail, "Big Thief")
        self.assertContains(detail, "Union Transfer")

    def test_detail_page_lists_other_fans_reviews_but_not_hidden_or_private_ones(self):
        riley = make_user("riley", display_name="Riley Okafor")
        log(riley, self.event, review="Muddy sound in the balcony.")
        sam = make_user("sam", is_private=True)
        log(sam, self.event, review="Private thoughts.")
        jo = make_user("jo")
        log(jo, self.event, review="Abusive text.", review_hidden=True)
        self.client.logout()
        resp = self.client.get(reverse("shows:detail", args=[self.event.pk]))
        self.assertContains(resp, "Muddy sound in the balcony.")
        self.assertContains(resp, "Riley Okafor")
        self.assertNotContains(resp, "Private thoughts.")
        self.assertNotContains(resp, "Abusive text.")

    def test_others_cannot_rate_or_review_my_entry(self):
        make_user("riley")
        self.client.login(username="riley", password=PASSWORD)
        self.assertEqual(self.rate("1.0").status_code, 404)
        self.assertEqual(self.client.post(self.review_url, {"review": "hijack"}).status_code, 404)
