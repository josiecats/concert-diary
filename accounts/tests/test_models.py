"""Model-level rules for Profile (US-1, US-2)."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import Profile
from shows.tests.factories import make_user

User = get_user_model()


class ProfileModelTests(TestCase):
    def test_profile_is_created_with_every_user_us1(self):
        user = User.objects.create_user("newfan", "new@example.com", "pw-12345678")
        self.assertIsInstance(user.profile, Profile)
        self.assertFalse(user.profile.is_private)
        self.assertIsNotNone(user.profile.created_at)

    def test_one_profile_per_user(self):
        user = make_user("mara")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Profile.objects.create(user=user)

    def test_username_is_unique_us1(self):
        make_user("mara")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("mara", "other@example.com", "pw-12345678")

    def test_deleting_a_user_deletes_their_profile(self):
        make_user("mara").delete()
        self.assertFalse(Profile.objects.exists())

    def test_name_falls_back_to_username_us2(self):
        user = make_user("mara")
        self.assertEqual(user.profile.name, "mara")
        user.profile.display_name = "Mara Lin"
        self.assertEqual(user.profile.name, "Mara Lin")
        self.assertEqual(user.profile.initials, "ML")

    def test_bio_is_capped_at_500_characters_us2(self):
        profile = make_user("mara").profile
        profile.bio = "x" * 500
        profile.full_clean()
        profile.bio = "x" * 501
        with self.assertRaises(ValidationError):
            profile.full_clean()

    def test_private_profile_is_visible_to_owner_only_us2(self):
        owner = make_user("mara", is_private=True)
        other = make_user("jo")
        self.assertTrue(owner.profile.visible_to(owner))
        self.assertFalse(owner.profile.visible_to(other))
        self.assertFalse(owner.profile.visible_to(AnonymousUser()))

    def test_public_profile_is_visible_to_everyone_us2(self):
        owner = make_user("mara")
        self.assertTrue(owner.profile.visible_to(AnonymousUser()))
        self.assertTrue(owner.profile.visible_to(make_user("jo")))
