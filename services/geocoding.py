"""Venue geocoding. Stands in for the Mapbox Geocoding API in the prototype.

Looks up exact venue coordinates first, then falls back to the city centre. An unknown
city returns None, so the show lands in "Not on the map" (US-10).
"""

from __future__ import annotations

import json

from django.conf import settings


def _tables():
    with open(settings.DEMO_SHOWS_FIXTURE) as f:
        return json.load(f)["geocoding"]


def geocode(venue_name: str, city: str) -> tuple[float, float] | None:
    tables = _tables()
    exact = tables["venues"].get(f"{venue_name.strip()}|{city.strip()}")
    if exact:
        return tuple(exact)
    for known_city, coords in tables["cities"].items():
        if known_city.lower() == city.strip().lower():
            return tuple(coords)
    return None
