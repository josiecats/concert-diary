from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from shows.tests.factories import PASSWORD, make_user

User = get_user_model()

GOOGLE_CONFIGURED = {
    "google": {
        "APPS": [{"client_id": "test-client-id", "secret": "test-secret", "key": ""}],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}
GOOGLE_UNCONFIGURED = {"google": {"APPS": []}}


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

    @override_settings(SOCIALACCOUNT_PROVIDERS=GOOGLE_UNCONFIGURED)
    def test_google_button_is_disabled_when_no_client_id_is_set(self):
        for name in ("account_signup", "account_login"):
            resp = self.client.get(reverse(name))
            self.assertContains(resp, "Continue with Google")
            self.assertContains(resp, 'aria-disabled="true"')
            self.assertNotContains(resp, reverse("google_login"))

    @override_settings(SOCIALACCOUNT_PROVIDERS=GOOGLE_CONFIGURED)
    def test_google_button_posts_to_google_login_when_configured(self):
        for name in ("account_signup", "account_login"):
            resp = self.client.get(reverse(name))
            self.assertContains(resp, f'action="{reverse("google_login")}"')
            self.assertNotContains(resp, 'aria-disabled="true"')

    @override_settings(SOCIALACCOUNT_PROVIDERS=GOOGLE_CONFIGURED)
    def test_google_login_redirects_to_google_with_client_id_from_settings(self):
        resp = self.client.post(reverse("google_login"))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].startswith("https://accounts.google.com/"), resp["Location"])
        self.assertIn("client_id=test-client-id", resp["Location"])

    def test_google_signups_choose_their_own_username(self):
        from django.conf import settings

        self.assertFalse(settings.SOCIALACCOUNT_AUTO_SIGNUP)
        self.assertIn("username*", settings.ACCOUNT_SIGNUP_FIELDS)
        self.assertEqual(settings.ACCOUNT_SIGNUP_REDIRECT_URL, reverse("accounts:onboarding"))

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
