"""Tiny helpers for building test data without fixtures."""

import itertools
from datetime import date

from django.contrib.auth import get_user_model

from shows.models import Artist, Attendance, Event, Venue

_seq = itertools.count(1)
PASSWORD = "test-pass-123"


def make_user(username="fan", **profile_fields):
    user = get_user_model().objects.create_user(username=username, email=f"{username}@example.com", password=PASSWORD)
    if profile_fields:
        for key, value in profile_fields.items():
            setattr(user.profile, key, value)
        user.profile.save()
    return user


def make_venue(name=None, city="Chicago", country="United States", lat=41.9, lng=-87.6, **kw):
    n = next(_seq)
    return Venue.objects.create(name=name or f"Venue {n}", city=city, country=country, lat=lat, lng=lng, **kw)


def make_event(artist="Big Thief", venue=None, event_date=date(2022, 4, 12), source=Event.SOURCE_SETLISTFM, **kw):
    artist_obj, _ = Artist.objects.get_or_create(name=artist, mbid=None)
    return Event.objects.create(
        artist=artist_obj, venue=venue or make_venue(), event_date=event_date, source=source,
        setlistfm_id=kw.pop("setlistfm_id", f"t{next(_seq):07d}" if source == Event.SOURCE_SETLISTFM else None),
        **kw,
    )


def log(user, event=None, **kw):
    return Attendance.objects.create(user=user, event=event or make_event(), **kw)
