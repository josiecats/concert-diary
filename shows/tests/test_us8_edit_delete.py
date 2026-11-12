from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from shows.models import Attendance
from shows.tests.factories import PASSWORD, log, make_event, make_user, make_venue


class US8EditDeleteTests(TestCase):
    """US-8: edit or delete my rating, review or log."""

    def setUp(self):
        self.user = make_user("mara")
        self.client.login(username="mara", password=PASSWORD)
        self.metro = make_venue("Metro", city="Chicago")
        self.att = log(self.user, make_event("Mitski", self.metro, date(2019, 3, 30)),
                       rating=Decimal("3.0"), review="Good, not great.", top3_rank=1)
        self.other = log(self.user, make_event("Big Thief", make_venue("Union Transfer", city="Philadelphia"),
                                               date(2022, 4, 12)), top3_rank=2)
        self.edit_url = reverse("shows:edit", args=[self.att.pk])
        self.delete_url = reverse("shows:delete", args=[self.att.pk])

    def test_can_edit_rating_and_review_of_any_logged_show(self):
        resp = self.client.get(self.edit_url)
        self.assertContains(resp, "Good, not great.")
        resp = self.client.post(self.edit_url, {"rating": "4.5", "review": "Grew on me. Best of the year."})
        self.assertRedirects(resp, reverse("shows:detail", args=[self.att.event_id]))
        self.att.refresh_from_db()
        self.assertEqual(self.att.rating, Decimal("4.5"))
        self.assertEqual(self.att.review, "Grew on me. Best of the year.")

    def test_edit_rejects_invalid_rating_and_overlong_review(self):
        resp = self.client.post(self.edit_url, {"rating": "3.3", "review": "x" * 5001})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("rating", resp.context["form"].errors)
        self.assertIn("review", resp.context["form"].errors)

    def test_edited_reviews_show_an_edited_label_with_the_date(self):
        self.client.post(self.edit_url, {"rating": "3.0", "review": "Changed my mind."})
        self.att.refresh_from_db()
        self.assertIsNotNone(self.att.review_edited_at)
        label = f"Edited {self.att.review_edited_at:%b} {self.att.review_edited_at.day}, {self.att.review_edited_at.year}"
        self.assertContains(self.client.get(reverse("shows:detail", args=[self.att.event_id])), label)
        self.assertContains(self.client.get(reverse("shows:diary", args=["mara"])), label)

    def test_changing_only_the_rating_does_not_mark_the_review_edited(self):
        self.client.post(self.edit_url, {"rating": "5.0", "review": "Good, not great."})
        self.att.refresh_from_db()
        self.assertIsNone(self.att.review_edited_at)

    def test_delete_asks_for_confirmation_first(self):
        resp = self.client.get(self.delete_url)
        self.assertContains(resp, "Delete Mitski at Metro")
        self.assertContains(resp, "removes it from your diary, stats, map and Top 3")
        self.assertTrue(Attendance.objects.filter(pk=self.att.pk).exists())

        partial = self.client.get(self.delete_url, HTTP_HX_REQUEST="true")
        self.assertNotContains(partial, "<html")
        self.assertContains(partial, "Yes, delete")

    def test_confirmed_delete_removes_it_from_diary_stats_map_and_top3(self):
        resp = self.client.post(self.delete_url, HTTP_HX_REQUEST="true")
        self.assertEqual(resp["HX-Redirect"], reverse("shows:diary", args=["mara"]))
        self.assertFalse(Attendance.objects.filter(pk=self.att.pk).exists())

        diary = self.client.get(reverse("shows:diary", args=["mara"]))
        self.assertNotIn(self.att.pk, [a.pk for a in diary.context["entries"]])
        profile = self.client.get(reverse("accounts:profile", args=["mara"]))
        self.assertEqual(profile.context["stats"]["shows"], 1)
        self.assertEqual([a.pk for a in profile.context["top3"]], [self.other.pk])
        self.other.refresh_from_db()
        self.assertEqual(self.other.top3_rank, 1)
        pins = self.client.get(reverse("maps:venues", args=["mara"])).json()["pins"]
        self.assertNotIn("Metro", [p["name"] for p in pins])

    def test_delete_without_htmx_redirects_to_diary_with_message(self):
        resp = self.client.post(self.delete_url, follow=True)
        self.assertRedirects(resp, reverse("shows:diary", args=["mara"]))
        self.assertContains(resp, "Deleted Mitski at Metro from your diary.")

    def test_only_the_author_can_edit_or_delete(self):
        make_user("riley")
        self.client.login(username="riley", password=PASSWORD)
        self.assertEqual(self.client.get(self.edit_url).status_code, 404)
        self.assertEqual(self.client.post(self.edit_url, {"rating": "1.0"}).status_code, 404)
        self.assertEqual(self.client.post(self.delete_url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.post(self.delete_url).status_code, 302)
        self.assertTrue(Attendance.objects.filter(pk=self.att.pk).exists())
