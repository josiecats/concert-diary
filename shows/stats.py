from django.db.models import Avg, Count
from django.db.models.functions import ExtractYear

from .models import Attendance


def lifetime_stats(user):
    """Totals for the profile header (US-2). Counted live so log/delete updates them."""
    qs = Attendance.objects.filter(user=user)
    avg = qs.aggregate(avg=Avg("rating"))["avg"]
    busiest = (
        qs.annotate(year=ExtractYear("event__event_date"))
        .values("year")
        .annotate(n=Count("id"))
        .order_by("-n", "-year")
        .first()
    )
    return {
        "shows": qs.count(),
        "artists": qs.values("event__artist").distinct().count(),
        "venues": qs.values("event__venue").distinct().count(),
        "cities": qs.values("event__venue__city", "event__venue__country").distinct().count(),
        "avg_rating": round(float(avg), 1) if avg is not None else None,
        "busiest_year": busiest["year"] if busiest else None,
        "busiest_year_shows": busiest["n"] if busiest else 0,
    }
