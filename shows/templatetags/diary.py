from decimal import Decimal

from django import template
from django.utils.html import format_html, format_html_join

register = template.Library()

_STAR = "M12 2l2.9 6.6 7.1.6-5.4 4.7 1.6 7L12 17.3 5.8 21l1.6-7L2 9.2l7.1-.6z"


@register.simple_tag
def stars(rating, size="1rem"):
    """Read-only star row with half stars. Screen readers get "4.5 out of 5 stars"."""
    if rating is None:
        return format_html('<span class="text-sm text-haze">Not rated</span>')
    value = Decimal(rating)
    parts = []
    for i in range(1, 6):
        fill = "1" if value >= i else ("0.5" if value >= i - Decimal("0.5") else "0")
        parts.append((fill, size, size, _STAR, _STAR))
    svgs = format_html_join(
        "",
        '<svg viewBox="0 0 24 24" aria-hidden="true" style="width:{1};height:{2}">'
        '<path d="{3}" fill="#3B2D52"/>'
        '<path d="{4}" fill="#D8B4FE" style="clip-path:inset(0 calc((1 - {0}) * 100%) 0 0)"/></svg>',
        parts,
    )
    label = f"{value.normalize():f} out of 5 stars"
    return format_html('<span class="inline-flex items-center gap-px" role="img" aria-label="{}">{}</span>', label, svgs)


@register.filter
def rating_display(value):
    return "" if value is None else f"{Decimal(value).normalize():f}"


@register.filter
def initials(name):
    """Up to two initials for an artist tile: "Noah Kahan" -> "NK", "Goose" -> "G"."""
    words = [w for w in str(name or "").split() if w[:1].isalnum()]
    return "".join(w[0] for w in words[:2]).upper() or "?"


@register.filter
def tile_class(name):
    """A stable colour for an artist's tile, so the same artist always looks the same."""
    return f"tile-{sum(map(ord, str(name or ''))) % 5}"


@register.filter
def average_rating(attendances):
    """Mean star rating of a list of attendances, ignoring unrated ones. None if none are rated."""
    rated = [a.rating for a in attendances if a.rating is not None]
    return round(float(sum(rated)) / len(rated), 1) if rated else None
