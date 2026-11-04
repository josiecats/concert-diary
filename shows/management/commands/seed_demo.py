"""Create a demo user with a populated diary. Safe to run more than once.

    python manage.py seed_demo
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from services import setlistfm
from shows.models import Artist, Attendance, Event, Venue

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo12345"

# (setlist.fm id, rating, top3_rank, review, edited)
DEMO_LOGS = [
    ("ce93038b", "5.0", 1, "Three voices, one mic, twenty thousand people singing \"Not Strong Enough\" back at them. "
     "I cried during \"Letter to an Old Poet\" and so did the guy next to me.", False),
    ("9f92d3bc", "4.5", 2, "Adrianne played \"Simulation Swarm\" alone first and the room went silent. "
     "Union Transfer is the perfect size for this band.", False),
    ("ef2f2378", "5.0", 3, "Nineteen songs into the encore and they still had \"Idioteque\" left. "
     "The light rig alone was worth the ticket.", False),
    ("ca7b1672", "4.5", None, "Golden hour at the Bowl, then \"I Know the End\" with the whole crowd screaming. "
     "Bring a jacket, it gets cold up top.", False),
    ("f6ba7970", "4.5", None, "Holiday residency night three. Danced for two and a half hours straight. "
     "Updated: \"All My Friends\" was the closer, not \"Home\".", True),
    ("5bb71453", "4.0", None, "First show at the Westcott. Tiny room, huge sound. Michelle threw a "
     "sing-along for \"Everybody Wants to Love You\".", False),
    ("aaa49e3b", "4.0", None, "Loud, fast and very Manchester. Grian barely moved and still owned the room.", False),
    ("875f0d86", "4.5", None, "Karly's guitar tone could strip paint. Hometown-adjacent crowd, lots of flannel.", False),
    ("1b352d4a", "3.5", None, "", False),
    ("cd79c16a", "4.0", None, "", False),
    ("c7679563", "3.5", None, "", False),
    ("937c1e65", "3.0", None, "", False),
    ("5a62083b", "4.0", None, "", False),
    ("cba2c06a", None, None, "", False),
]

# A second fan, so show pages have other people's reviews to read.
OTHER_USERNAME = "riley"
OTHER_LOGS = [
    ("ce93038b", "4.5", "Worth the nosebleed seats. The Phoebe/Julien harmony on \"Cool About It\" got me.", False),
    ("ef2f2378", "4.0", "Thom in a great mood, which is rare. Sound was muddy in section 112 though.", False),
    ("9f92d3bc", "1.0", "This review breaks the community guidelines.", True),  # hidden by a moderator
]


class Command(BaseCommand):
    help = "Create the demo user (demo / demo12345) with 15 logged shows, ratings, reviews and a Top 3."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        demo, _ = User.objects.get_or_create(username=DEMO_USERNAME, defaults={"email": "demo@example.com"})
        demo.set_password(DEMO_PASSWORD)
        demo.date_joined = timezone.now() - timedelta(days=210)
        demo.save()
        profile = demo.profile
        profile.display_name = "Mara Quinn"
        profile.bio = "Front-row optimist. Indie rock, big choruses, small rooms. Still chasing a perfect setlist."
        profile.home_city = "Syracuse, NY"
        profile.is_private = False
        profile.save()

        Attendance.objects.filter(user=demo).delete()
        now = timezone.now()
        for setlist_id, rating, rank, review, edited in DEMO_LOGS:
            event = setlistfm.cache_event(setlist_id)
            Attendance.objects.create(
                user=demo,
                event=event,
                rating=Decimal(rating) if rating else None,
                review=review,
                top3_rank=rank,
                review_edited_at=now - timedelta(days=12) if edited else None,
            )

        # One user-added show in a city the geocoder doesn't know, so it lands in "Not on the map".
        artist, _ = Artist.objects.get_or_create(mbid=None, name="Salt Lick Choir")
        venue, _ = Venue.objects.get_or_create(
            setlistfm_id=None, name="Cayuga Street Basement", city="Ithaca",
            defaults={"country": "United States", "created_by": demo},
        )
        event, _ = Event.objects.get_or_create(
            artist=artist, venue=venue, event_date=date(2024, 8, 30),
            defaults={"source": Event.SOURCE_USER, "created_by": demo},
        )
        Attendance.objects.create(
            user=demo, event=event, rating=Decimal("4.0"),
            review="Friend's band, forty people, one box fan. Best $5 I spent all summer.",
        )

        other, _ = User.objects.get_or_create(username=OTHER_USERNAME, defaults={"email": "riley@example.com"})
        other.set_password(DEMO_PASSWORD)
        other.save()
        other.profile.display_name = "Riley Okafor"
        other.profile.home_city = "Brooklyn, NY"
        other.profile.save()
        Attendance.objects.filter(user=other).delete()
        for setlist_id, rating, review, hidden in OTHER_LOGS:
            Attendance.objects.create(
                user=other, event=setlistfm.cache_event(setlist_id),
                rating=Decimal(rating), review=review, review_hidden=hidden,
            )

        count = Attendance.objects.filter(user=demo).count()
        if options["verbosity"] > 0:
            self.stdout.write(self.style.SUCCESS(
            f"Seeded {count} shows for '{DEMO_USERNAME}' (password: {DEMO_PASSWORD}). Profile: /u/{DEMO_USERNAME}/"
        ))
