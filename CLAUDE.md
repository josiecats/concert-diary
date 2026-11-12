# Concert Diary

A web app for logging live shows ("Letterboxd for concerts"). V1 is a free, single-player diary: profiles, setlist.fm search and logging, ratings and reviews, Top 3, and a venue map. V2 adds premium meetups and is **out of scope** until the PRD says otherwise.

## Rules

- Visual source of truth: design/ (screenshots of the prototype). Match colors, type, spacing.
- Palette: bg #0E0818, text #F7F3FF, muted #BBB0D6, lilac #D8B4FE, violet #6D28D9, light #DDD6FE.
- Fonts: Space Grotesk (headings), Inter (body). White primary buttons, rounded 12px.
- PRD.md is the source of truth for requirements. Reference user story IDs (US-x) in commits and tests.
- Use HTMX partial templates for interactive actions. No React or other JS framework.
- Never put API keys in code. Read them from `.env` via django-environ.
- Run `python manage.py test` before every commit.

## Tech stack

| Layer | Choice |
| --- | --- |
| Framework | Django 5 (Python) |
| Pages | Django templates + HTMX + Tailwind CSS (or Pico.css) |
| Database | PostgreSQL via the Django ORM (SQLite while prototyping) |
| Cache | Django cache framework (Redis in production) |
| Auth | Django auth + django-allauth (email + Google OAuth) |
| Moderation | Django admin (US-11) |
| Map | Leaflet + OpenStreetMap tiles, fed by a JSON view |
| Geocoding | Mapbox Geocoding API (venue name + city → lat/lng) |
| Show data | setlist.fm API, via `services/setlistfm.py` using `requests` |
| Artist data | MusicBrainz |
| Config | django-environ reading `.env` |
| Hosting | Render |

## Django app structure

- `accounts`: Profile model, sign-up, onboarding, public profile at `/u/<username>`, privacy setting, lifetime stats (US-1, US-2)
- `shows`: Artist, Venue, Event, Attendance and Report models; search, log, manual entry, diary list, rate/review, edit/delete, Top 3, reporting (US-3 to US-9, US-11)
- `maps`: venue JSON endpoint and the map page (US-10)
- `services/setlistfm.py`: the only place that calls setlist.fm

Partial templates for HTMX responses live alongside each app's templates (e.g. `shows/templates/shows/partials/`).

## Data model notes

- Events, artists and venues are cached in Postgres the first time someone logs them; check the local cache before calling setlist.fm.
- `Attendance` is unique on `(user, event)`; logging the same event twice must be blocked (US-4).
- `Attendance.top3_rank` is 1–3 or null. Deleting an attendance removes it from the diary, stats, map and Top 3 (US-8, US-9).
- `Event.source` is `setlistfm` or `user`; user-added shows count in stats and on the map (US-5).
- Ratings are optional, half-star steps from 0.5 to 5. Reviews are optional, max 5,000 characters (US-7).
- Hidden reviews disappear from public views but stay visible to their author (US-11).

## External API notes

- setlist.fm requires an `x-api-key` header. Call it only from the server.
- setlist.fm rate limits are tight: cache every fetched event, artist and venue, and debounce search input.
- setlist.fm gives only city coordinates, so venues are geocoded with Mapbox.
