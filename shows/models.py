from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.db.models.signals import m2m_changed
from django.dispatch import receiver

REVIEW_MAX_LENGTH = 5000
TAG_MAX_LENGTH = 24
PREMADE_TAGS = [
    "Setlist was perfect",
    "Great sound",
    "Wild crowd",
    "In the pit",
    "With friends",
    "Surprise guest",
    "Cried a little",
    "Would go again",
]
RATING_CHOICES = [(Decimal(n) / 2).quantize(Decimal("0.1")) for n in range(1, 11)]  # 0.5, 1.0 .. 5.0


def validate_half_star(value):
    if value is None:
        return
    if value not in RATING_CHOICES:
        raise ValidationError("Ratings go from 0.5 to 5 in half-star steps.")


class Artist(models.Model):
    mbid = models.CharField("MusicBrainz ID", max_length=36, unique=True, null=True, blank=True)
    name = models.CharField(max_length=200)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Venue(models.Model):
    setlistfm_id = models.CharField(max_length=32, unique=True, null=True, blank=True)
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=120)
    country = models.CharField(max_length=120, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}, {self.city}"

    @property
    def has_coords(self):
        return self.lat is not None and self.lng is not None


class Event(models.Model):
    SOURCE_SETLISTFM = "setlistfm"
    SOURCE_USER = "user"
    SOURCE_CHOICES = [(SOURCE_SETLISTFM, "setlist.fm"), (SOURCE_USER, "User-added")]

    setlistfm_id = models.CharField(max_length=32, unique=True, null=True, blank=True)
    artist = models.ForeignKey(Artist, on_delete=models.PROTECT, related_name="events")
    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, related_name="events")
    event_date = models.DateField()
    tour_name = models.CharField(max_length=200, blank=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_SETLISTFM)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-event_date"]

    def __str__(self):
        return f"{self.artist} at {self.venue} on {self.event_date:%b %-d, %Y}"

    @property
    def is_user_added(self):
        return self.source == self.SOURCE_USER


class TagQuerySet(models.QuerySet):
    def premade(self):
        return self.filter(owner__isnull=True)

    def available_to(self, user):
        """Premade tags plus the user's own custom tags."""
        if user is None or not user.is_authenticated:
            return self.premade()
        return self.filter(Q(owner__isnull=True) | Q(owner=user))


class Tag(models.Model):
    """A "What made it" tag (US-7). No owner = premade; an owner = that user's custom tag."""

    name = models.CharField(max_length=TAG_MAX_LENGTH)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="custom_tags"
    )

    objects = TagQuerySet.as_manager()

    class Meta:
        ordering = ["owner_id", "name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"), condition=Q(owner__isnull=True), name="unique_premade_tag_name"
            ),
            models.UniqueConstraint(
                Lower("name"), "owner", condition=Q(owner__isnull=False), name="unique_custom_tag_name_per_owner"
            ),
        ]

    def __str__(self):
        return self.name if self.is_premade else f"# {self.name}"

    @property
    def is_premade(self):
        return self.owner_id is None

    def clean(self):
        self.name = (self.name or "").strip()
        if not self.name:
            raise ValidationError({"name": "Tags can't be blank."})
        if self.owner_id and Tag.objects.premade().filter(name__iexact=self.name).exists():
            raise ValidationError({"name": "That tag already exists. Pick it from the list instead."})


class AttendanceQuerySet(models.QuerySet):
    def with_related(self):
        return self.select_related("event__artist", "event__venue", "user__profile")

    def visible_reviews_for(self, viewer):
        """Hidden reviews stay visible to their author only (US-11)."""
        qs = self.exclude(review="")
        if viewer.is_authenticated:
            return qs.filter(Q(review_hidden=False) | Q(user=viewer))
        return qs.filter(review_hidden=False)


class Attendance(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="attendances")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="attendances")
    rating = models.DecimalField(
        max_digits=2, decimal_places=1, null=True, blank=True, validators=[validate_half_star]
    )
    # TextField max_length only applies to forms; the validator enforces it on full_clean() too.
    review = models.TextField(max_length=REVIEW_MAX_LENGTH, blank=True, validators=[MaxLengthValidator(REVIEW_MAX_LENGTH)])
    review_edited_at = models.DateTimeField(null=True, blank=True)
    review_has_spoilers = models.BooleanField("Contains setlist spoilers", default=False)
    review_hidden = models.BooleanField(default=False)
    tags = models.ManyToManyField(Tag, blank=True, related_name="attendances")
    top3_rank = models.PositiveSmallIntegerField(null=True, blank=True, choices=[(1, "1"), (2, "2"), (3, "3")])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AttendanceQuerySet.as_manager()

    class Meta:
        ordering = ["-event__event_date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "event"], name="unique_attendance_per_user_event"),
            models.UniqueConstraint(
                fields=["user", "top3_rank"],
                condition=Q(top3_rank__isnull=False),
                name="unique_top3_rank_per_user",
            ),
            models.CheckConstraint(
                condition=Q(top3_rank__isnull=True) | Q(top3_rank__gte=1, top3_rank__lte=3),
                name="top3_rank_between_1_and_3",
            ),
        ]

    def __str__(self):
        return f"{self.user} attended {self.event}"


@receiver(m2m_changed, sender=Attendance.tags.through)
def block_other_users_custom_tags(sender, instance, action, reverse, pk_set, **kwargs):
    """An attendance can use premade tags and its owner's custom tags only."""
    if action != "pre_add" or not pk_set:
        return
    if reverse:
        # tag.attendances.add(...): instance is the Tag, pk_set holds attendance ids.
        if instance.owner_id and Attendance.objects.filter(pk__in=pk_set).exclude(user_id=instance.owner_id).exists():
            raise ValidationError("A custom tag can only be used by the person who made it.")
        return
    foreign = Tag.objects.filter(pk__in=pk_set, owner__isnull=False).exclude(owner_id=instance.user_id)
    if foreign.exists():
        raise ValidationError("A custom tag can only be used by the person who made it.")


class Report(models.Model):
    STATUS_OPEN = "open"
    STATUS_HIDDEN = "hidden"
    STATUS_DISMISSED = "dismissed"
    STATUS_CHOICES = [(STATUS_OPEN, "Open"), (STATUS_HIDDEN, "Review hidden"), (STATUS_DISMISSED, "Dismissed")]

    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_made")
    reason = models.CharField(max_length=500)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report on {self.attendance_id} ({self.status})"
