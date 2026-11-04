"""The only place that talks to setlist.fm.

The prototype uses MockSetlistClient, which reads fixtures/demo_shows.json (same shape as
the setlist.fm `search/setlists` response). RealSetlistClient is a stub for milestone 5.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from services import geocoding

SEARCH_CACHE_SECONDS = 60 * 60
MIN_QUERY_LENGTH = 2


@dataclass(frozen=True)
class SetlistResult:
    """One search result, normalized from a setlist.fm setlist."""

    id: str
    artist_name: str
    artist_mbid: str
    event_date: date
    venue_id: str
    venue_name: str
    city: str
    country: str
    tour_name: str

    @classmethod
    def from_api(cls, s: dict) -> "SetlistResult":
        venue = s["venue"]
        city = venue["city"]
        return cls(
            id=s["id"],
            artist_name=s["artist"]["name"],
            artist_mbid=s["artist"].get("mbid", ""),
            event_date=datetime.strptime(s["eventDate"], "%d-%m-%Y").date(),
            venue_id=venue["id"],
            venue_name=venue["name"],
            city=city["name"],
            country=city.get("country", {}).get("name", ""),
            tour_name=(s.get("tour") or {}).get("name", ""),
        )


@lru_cache(maxsize=4)
def _load_fixture(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


class MockSetlistClient:
    """Answers searches from the demo fixture instead of the API."""

    def __init__(self, path=None):
        self.path = str(path or settings.DEMO_SHOWS_FIXTURE)

    def _setlists(self):
        return _load_fixture(self.path)["setlist"]

    def search(self, artist: str, year: int | None = None, venue: str = "", city: str = ""):
        artist, venue, city = artist.strip().lower(), venue.strip().lower(), city.strip().lower()
        results = []
        for s in self._setlists():
            r = SetlistResult.from_api(s)
            if artist not in r.artist_name.lower():
                continue
            if year and r.event_date.year != year:
                continue
            if venue and venue not in r.venue_name.lower():
                continue
            if city and city not in r.city.lower():
                continue
            results.append(r)
        return sorted(results, key=lambda r: r.event_date, reverse=True)

    def get(self, setlist_id: str) -> SetlistResult | None:
        for s in self._setlists():
            if s["id"] == setlist_id:
                return SetlistResult.from_api(s)
        return None


class RealSetlistClient:
    """Placeholder for the live API (milestone 5). Sends the key server-side only."""

    BASE_URL = "https://api.setlist.fm/rest/1.0"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.SETLISTFM_API_KEY

    @property
    def headers(self):
        return {"x-api-key": self.api_key, "Accept": "application/json"}

    def search(self, artist, year=None, venue="", city=""):
        raise NotImplementedError("Live setlist.fm search ships in milestone 5.")

    def get(self, setlist_id):
        raise NotImplementedError("Live setlist.fm lookup ships in milestone 5.")


def get_client():
    if settings.SETLISTFM_CLIENT == "real":
        return RealSetlistClient()
    return MockSetlistClient()


def search(artist: str, year: int | None = None, venue: str = "", city: str = ""):
    """Search with a cache in front, so repeat queries never hit the API."""
    if len(artist.strip()) < MIN_QUERY_LENGTH:
        return []
    raw = "|".join([artist.strip().lower(), str(year or ""), venue.strip().lower(), city.strip().lower()])
    key = "setlistfm:search:" + hashlib.sha1(raw.encode()).hexdigest()
    results = cache.get(key)
    if results is None:
        results = get_client().search(artist, year=year, venue=venue, city=city)
        cache.set(key, results, SEARCH_CACHE_SECONDS)
    return results


@transaction.atomic
def cache_event(setlist_id: str):
    """Return the local Event for a setlist.fm id, fetching and caching it on first use."""
    from shows.models import Artist, Event, Venue

    event = Event.objects.select_related("artist", "venue").filter(setlistfm_id=setlist_id).first()
    if event:
        return event

    result = get_client().get(setlist_id)
    if result is None:
        return None

    if result.artist_mbid:
        artist, _ = Artist.objects.get_or_create(mbid=result.artist_mbid, defaults={"name": result.artist_name})
    else:
        artist, _ = Artist.objects.get_or_create(mbid=None, name=result.artist_name)
    venue = Venue.objects.filter(setlistfm_id=result.venue_id).first()
    if venue is None:
        lat, lng = geocoding.geocode(result.venue_name, result.city) or (None, None)
        venue = Venue.objects.create(
            setlistfm_id=result.venue_id,
            name=result.venue_name,
            city=result.city,
            country=result.country,
            lat=lat,
            lng=lng,
        )
    return Event.objects.create(
        setlistfm_id=result.id,
        artist=artist,
        venue=venue,
        event_date=result.event_date,
        tour_name=result.tour_name,
        source=Event.SOURCE_SETLISTFM,
    )
