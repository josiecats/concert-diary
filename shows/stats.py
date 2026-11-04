from .models import Attendance


def lifetime_stats(user):
    """Totals for the profile header (US-2). Counted live so log/delete updates them."""
    qs = Attendance.objects.filter(user=user)
    return {
        "shows": qs.count(),
        "artists": qs.values("event__artist").distinct().count(),
        "venues": qs.values("event__venue").distinct().count(),
        "cities": qs.values("event__venue__city", "event__venue__country").distinct().count(),
    }
