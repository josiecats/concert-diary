from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from shows.tests.clickthrough import ClickThroughMixin


class ProfileClickThroughTests(ClickThroughMixin, TestCase):
    """Screen 2: click through the seeded demo profile as owner and as a visitor."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def test_visitor_sees_populated_profile_and_every_link_works(self):
        resp = self.client.get(reverse("accounts:profile", args=["demo"]))
        self.assertEqual(resp.status_code, 200)
        self.assertAccessiblePage(resp)
        self.assertContains(resp, "Mara Quinn")
        self.assertContains(resp, 'data-stat="shows">15<')
        for artist in ("boygenius", "Big Thief", "Radiohead"):
            self.assertContains(resp, artist)
        self.assertContains(resp, "Not on the map")
        self.assertNotContains(resp, "Edit Top 3")
        self.assertLinksResolve(resp)

    def test_owner_flow_profile_to_top3_editor_and_back(self):
        self.client.login(username="demo", password="demo12345")
        resp = self.client.get(reverse("accounts:profile", args=["demo"]))
        self.assertAccessiblePage(resp)
        self.assertContains(resp, "Edit Top 3")
        self.assertContains(resp, "Fix location")
        links = self.assertLinksResolve(resp)
        for name in ("accounts:settings", "shows:top3", "shows:search", "shows:diary"):
            args = ["demo"] if name == "shows:diary" else []
            self.assertIn(reverse(name, args=args), links)

        editor = self.client.get(reverse("shows:top3"))
        self.assertAccessiblePage(editor)
        partial = self.client.post(
            reverse("shows:top3_move", args=[editor.context["top3"][1].pk, "up"]), HTTP_HX_REQUEST="true"
        )
        self.assertNotContains(partial, "<html")  # HTMX gets a fragment, not a page
        self.assertContains(partial, 'id="top3-editor"')

    def test_fix_location_form_partial_is_labelled(self):
        self.client.login(username="demo", password="demo12345")
        profile = self.client.get(reverse("accounts:profile", args=["demo"]))
        venue_id = profile.context["not_on_map"][0].event.venue_id
        form = self.client.get(reverse("maps:fix_location", args=[venue_id]), HTTP_HX_REQUEST="true")
        self.assertAccessiblePage(form)
        self.assertContains(form, "Latitude (optional)")

    def test_venue_json_for_demo_has_pins_in_many_cities(self):
        data = self.client.get(reverse("maps:venues", args=["demo"])).json()
        self.assertGreaterEqual(len({p["city"] for p in data["pins"]}), 8)
        self.assertEqual(data["unmapped"], 1)
