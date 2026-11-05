"""Seed the premade "What made it" tags from the design (US-7)."""

from django.db import migrations

# Frozen copy: later edits to shows.models.PREMADE_TAGS need their own migration.
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


def seed(apps, schema_editor):
    Tag = apps.get_model("shows", "Tag")
    for name in PREMADE_TAGS:
        if not Tag.objects.filter(owner__isnull=True, name__iexact=name).exists():
            Tag.objects.create(name=name, owner=None)


def unseed(apps, schema_editor):
    Tag = apps.get_model("shows", "Tag")
    Tag.objects.filter(owner__isnull=True, name__in=PREMADE_TAGS).delete()


class Migration(migrations.Migration):
    dependencies = [("shows", "0002_attendance_spoilers_and_tags")]

    operations = [migrations.RunPython(seed, unseed)]
