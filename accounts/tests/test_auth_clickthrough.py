from django.test import TestCase
from django.urls import reverse

from shows.tests.clickthrough import ClickThroughMixin


class AuthClickThroughTests(ClickThroughMixin, TestCase):
    """Screen 1: landing -> sign up -> onboarding -> search, all reachable and labelled."""

    def test_signup_to_first_search(self):
        landing = self.client.get(reverse("home"))
        self.assertAccessiblePage(landing)
        self.assertLinksResolve(landing)

        signup = self.client.get(reverse("account_signup"))
        self.assertAccessiblePage(signup)
        self.assertAccessiblePage(self.client.get(reverse("account_login")))

        resp = self.client.post(reverse("account_signup"), {
            "email": "pat@example.com", "username": "pat", "password1": "big-chorus-99", "password2": "big-chorus-99",
        }, follow=True)
        self.assertEqual(resp.request["PATH_INFO"], reverse("accounts:onboarding"))
        self.assertAccessiblePage(resp)
        self.assertLinksResolve(resp)

        search = self.client.get(reverse("shows:search"), {"artist": "mitski"})
        self.assertContains(search, "3 shows found")

    def test_nav_reaches_all_six_screens_when_logged_in(self):
        self.client.post(reverse("account_signup"), {
            "email": "pat@example.com", "username": "pat", "password1": "big-chorus-99", "password2": "big-chorus-99",
        })
        page = self.client.get(reverse("accounts:profile", args=["pat"]))
        links = self.assertLinksResolve(page)
        for url in (reverse("accounts:profile", args=["pat"]), reverse("shows:diary", args=["pat"]),
                    reverse("shows:search"), reverse("accounts:settings")):
            self.assertIn(url, links)
