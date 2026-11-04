from django.db.models.signals import post_delete
from django.dispatch import receiver

from . import top3
from .models import Attendance


@receiver(post_delete, sender=Attendance)
def close_top3_gap(sender, instance, **kwargs):
    """Deleting a log removes it from Top 3 (US-8, US-9); the rest move up."""
    # Always compact: the in-memory instance may hold a stale rank.
    top3.compact(instance.user_id)
