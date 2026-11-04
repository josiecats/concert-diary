from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from shows.tests.factories import PASSWORD, make_user

User = get_user_model()


class US1SignUpTests(TestCase):
    """US-1: sign up with email or Google and start a diary in under a minute."""

    def signup(self, **overrides):
        data = {"email": "new@example.com", "username": "newfan", "password1": "loud-guitars-42",
                "password2": "loud-guitars-42", **overrides}
        return self.client.post(reverse("account_signup"), data)

    def test_signup_supports_email_and_password(self):
        resp = self.signup()
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="newfan")
        self.assertEqual(user.email, "new@example.com")
        self.assertTrue(user.check_password("loud-guitars-42"))
        self.assertTrue(hasattr(user, "profile"))

    def test_signup_page_shows_google_option_marked_coming_soon(self):
        resp = self.client.get(reverse("account_signup"))
        self.assertContains(resp, "Continue with Google")
        self.assertContains(resp, 'aria-disabled="true"')
        self.assertContains(resp, "Google sign-in is coming soon")

    def test_after_signup_land_on_onboarding_that_prompts_first_log(self):
        resp = self.signup()
        self.assertRedirects(resp, reverse("accounts:onboarding"))
        page = self.client.get(reverse("accounts:onboarding"))
        self.assertContains(page, "Log your first show")
        self.assertContains(page, f'action="{reverse("shows:search")}"')

    def test_username_is_required(self):
        resp = self.signup(username="")
        self.assertIn("username", resp.context["form"].errors)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_username_must_be_unique_ignoring_case(self):
        make_user("newfan")
        resp = self.signup(username="NewFan", email="other@example.com")
        self.assertIn("username", resp.context["form"].errors)

    def test_username_must_be_url_safe(self):
        resp = self.signup(username="new fan!")
        self.assertIn("username", resp.context["form"].errors)

    def test_username_is_used_in_profile_url(self):
        self.signup()
        resp = self.client.get("/u/newfan/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "@newfan")

    def test_can_log_in_with_email_or_username(self):
        make_user("mara")
        for login in ("mara", "mara@example.com"):
            self.client.logout()
            resp = self.client.post(reverse("account_login"), {"login": login, "password": PASSWORD})
            self.assertEqual(resp.status_code, 302, login)
            self.assertEqual(self.client.get(reverse("home")).url, reverse("accounts:profile", args=["mara"]))

    def test_landing_page_invites_signup_and_shows_demo(self):
        self.assertNotContains(self.client.get(reverse("home")), "/u/demo/")  # no dead link before seeding
        call_command("seed_demo", verbosity=0)
        resp = self.client.get(reverse("home"))
        self.assertContains(resp, "Mara Quinn's Top 3")
        self.assertContains(resp, reverse("account_signup"))
        self.assertContains(resp, reverse("accounts:profile", args=["demo"]))
