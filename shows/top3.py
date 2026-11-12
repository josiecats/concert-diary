"""Top 3 ordering (US-9). Ranks are 1..3 with no gaps; a unique constraint guards (user, rank)."""

from django.db import transaction

from .models import Attendance

MAX_RANK = 3


class Top3Full(Exception):
    pass


def top3_for(user):
    return list(
        Attendance.objects.with_related().filter(user=user, top3_rank__isnull=False).order_by("top3_rank")
    )


@transaction.atomic
def add(attendance):
    if attendance.top3_rank:
        return
    taken = set(
        Attendance.objects.select_for_update()
        .filter(user=attendance.user_id, top3_rank__isnull=False)
        .values_list("top3_rank", flat=True)
    )
    free = [r for r in range(1, MAX_RANK + 1) if r not in taken]
    if not free:
        raise Top3Full
    attendance.top3_rank = free[0]
    attendance.save(update_fields=["top3_rank"])


@transaction.atomic
def move(attendance, direction):
    if not attendance.top3_rank:
        return
    target = attendance.top3_rank + (-1 if direction == "up" else 1)
    neighbour = Attendance.objects.filter(user=attendance.user_id, top3_rank=target).first()
    if neighbour is None:
        return
    old = attendance.top3_rank
    # Step through null to keep the unique (user, rank) constraint happy.
    Attendance.objects.filter(pk=attendance.pk).update(top3_rank=None)
    Attendance.objects.filter(pk=neighbour.pk).update(top3_rank=old)
    Attendance.objects.filter(pk=attendance.pk).update(top3_rank=target)


@transaction.atomic
def remove(attendance):
    Attendance.objects.filter(pk=attendance.pk).update(top3_rank=None)
    compact(attendance.user_id)


def compact(user_id):
    """Close gaps so ranks stay 1..n after a removal or delete."""
    ranked = Attendance.objects.filter(user=user_id, top3_rank__isnull=False).order_by("top3_rank")
    for new_rank, att in enumerate(ranked, start=1):
        if att.top3_rank != new_rank:
            Attendance.objects.filter(pk=att.pk).update(top3_rank=new_rank)
