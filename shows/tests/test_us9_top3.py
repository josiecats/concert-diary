from datetime import date

from django.test import TestCase
from django.urls import reverse

from shows.models import Attendance
from shows.tests.factories import PASSWORD, log, make_event, make_user, make_venue


class US9Top3Tests(TestCase):
    """US-9: pick and order my Top 3 shows."""

    def setUp(self):
        self.user = make_user("mara")
        self.client.login(username="mara", password=PASSWORD)
        self.a = log(self.user, make_event("boygenius", make_venue("Madison Square Garden", city="New York"), date(2023, 8, 4)))
        self.b = log(self.user, make_event("Big Thief", make_venue("Union Transfer", city="Philadelphia"), date(2022, 4, 12)))
        self.c = log(self.user, make_event("Radiohead", make_venue("Royal Albert Hall", city="London"), date(2018, 7, 27)))
        self.d = log(self.user, make_event("Mitski", make_venue("Metro"), date(2019, 3, 30)))

    def add(self, att):
        return self.client.post(reverse("shows:top3_add", args=[att.pk]), HTTP_HX_REQUEST="true")

    def ranks(self):
        return list(
            Attendance.objects.filter(user=self.user, top3_rank__isnull=False)
            .order_by("top3_rank").values_list("pk", flat=True)
        )

    def test_can_choose_up_to_three_logged_shows(self):
        for att in (self.a, self.b, self.c):
            self.assertEqual(self.add(att).status_code, 200)
        self.assertEqual(self.ranks(), [self.a.pk, self.b.pk, self.c.pk])

        resp = self.add(self.d)
        self.assertContains(resp, "Your Top 3 is full", status_code=409)
        self.assertEqual(self.ranks(), [self.a.pk, self.b.pk, self.c.pk])

    def test_can_only_choose_from_my_own_logged_shows(self):
        other = make_user("riley")
        theirs = log(other, self.a.event)
        self.assertEqual(self.add(theirs).status_code, 404)
        self.assertEqual(self.ranks(), [])

    def test_can_reorder_with_up_and_down_controls(self):
        for att in (self.a, self.b, self.c):
            self.add(att)
        resp = self.client.post(reverse("shows:top3_move", args=[self.c.pk, "up"]), HTTP_HX_REQUEST="true")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.ranks(), [self.a.pk, self.c.pk, self.b.pk])

        self.client.post(reverse("shows:top3_move", args=[self.a.pk, "down"]), HTTP_HX_REQUEST="true")
        self.assertEqual(self.ranks(), [self.c.pk, self.a.pk, self.b.pk])

        # Moving the top show up is a no-op, not an error.
        self.client.post(reverse("shows:top3_move", args=[self.c.pk, "up"]), HTTP_HX_REQUEST="true")
        self.assertEqual(self.ranks(), [self.c.pk, self.a.pk, self.b.pk])

    def test_editor_controls_have_accessible_labels(self):
        self.add(self.a)
        self.add(self.b)
        resp = self.client.get(reverse("shows:top3"))
        self.assertContains(resp, 'aria-label="Move boygenius up"')
        self.assertContains(resp, 'aria-label="Move boygenius down"')
        self.assertContains(resp, 'aria-label="Remove boygenius from Top 3"')

    def test_top3_appears_at_top_of_profile_with_artist_date_and_venue(self):
        for att in (self.b, self.a, self.c):
            self.add(att)
        html = self.client.get(reverse("accounts:profile", args=["mara"])).content.decode()
        top3 = html[html.index('id="top3"'):html.index('id="stats"')]
        self.assertLess(top3.index("Big Thief"), top3.index("boygenius"))
        self.assertLess(top3.index("boygenius"), top3.index("Radiohead"))
        self.assertIn("Union Transfer", top3)
        self.assertIn("Apr 12, 2022", top3)
        self.assertLess(html.index('id="top3"'), html.index('id="map"'))

    def test_removing_a_show_from_diary_removes_it_from_top3_and_closes_the_gap(self):
        for att in (self.a, self.b, self.c):
            self.add(att)
        self.a.delete()
        self.assertEqual(self.ranks(), [self.b.pk, self.c.pk])
        self.b.refresh_from_db()
        self.assertEqual(self.b.top3_rank, 1)

    def test_remove_control_takes_show_out_of_top3_only(self):
        self.add(self.a)
        self.add(self.b)
        self.client.post(reverse("shows:top3_remove", args=[self.a.pk]), HTTP_HX_REQUEST="true")
        self.assertEqual(self.ranks(), [self.b.pk])
        self.assertTrue(Attendance.objects.filter(pk=self.a.pk).exists())

    def test_top3_editor_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("shows:top3"))
        self.assertEqual(resp.status_code, 302)
