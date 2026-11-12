from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from shows.models import Attendance, Event


class SeedDemoTests(TestCase):
    def test_seed_creates_demo_diary(self):
        call_command("seed_demo", verbosity=0)
        demo = get_user_model().objects.get(username="demo")
        logs = Attendance.objects.filter(user=demo)
        self.assertEqual(logs.count(), 15)
        self.assertEqual(
            list(logs.filter(top3_rank__isnull=False).order_by("top3_rank").values_list("top3_rank", flat=True)),
            [1, 2, 3],
        )
        self.assertGreaterEqual(logs.exclude(review="").count(), 8)
        self.assertTrue(logs.filter(event__source=Event.SOURCE_USER).exists())
        self.assertGreaterEqual(logs.values("event__venue__city").distinct().count(), 8)

    def test_seed_is_idempotent(self):
        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)
        self.assertEqual(Attendance.objects.filter(user__username="demo").count(), 15)
