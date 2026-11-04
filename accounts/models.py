from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    """Public profile for a diary owner (US-2)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    display_name = models.CharField(max_length=80, blank=True)
    avatar_url = models.URLField(blank=True)
    bio = models.TextField(max_length=500, blank=True)
    home_city = models.CharField(max_length=120, blank=True)
    is_private = models.BooleanField(
        default=False, help_text="Private profiles are visible only to their owner."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def name(self):
        return self.display_name or self.user.username

    @property
    def initials(self):
        parts = self.name.split()
        return "".join(p[0] for p in parts[:2]).upper() or "?"

    def visible_to(self, viewer):
        """Private profiles are visible to their owner only."""
        return not self.is_private or (viewer.is_authenticated and viewer.pk == self.user_id)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)
