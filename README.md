# Concert Diary (v1 prototype)

A clickable prototype of Concert Diary, a "Letterboxd for concerts". It covers all six v1 screens from [PRD.md](PRD.md), built with Django templates, HTMX and Tailwind (CDN). It runs on mock setlist.fm data and makes no real API calls.

This is milestone 2 in the PRD: the build you put in front of 5 users for the usability test.

## Setup

You need Python 3.11.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # defaults work; no API keys needed for the mock

.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver
```

Open http://127.0.0.1:8000/u/demo/ to see the populated demo profile.

- **Demo login:** username `demo`, password `demo12345`. This is Mara Quinn: 15 shows, ratings, 9 reviews, a Top 3, and one user-added show that isn't on the map yet.
- **Second user:** `riley` with the same password, so show pages have other fans' reviews.
- **Resetting the demo:** `seed_demo` is safe to run again. It resets the demo diary and the demo password.
- **Password-reset emails** print to the `runserver` console.
- **Google sign-in (optional):** create an OAuth client in Google Cloud Console with the redirect URI `http://localhost:8000/accounts/google/login/callback/`, then set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`. Without them, the Google button is shown disabled.

### Tests

```bash
.venv/bin/python manage.py test          # 151 tests
```

Each user story has its own test file, with one test per acceptance criterion. Examples: `accounts/tests/test_us2_profile.py` and `shows/tests/test_us4_log.py`.

Model rules (constraints, validators, tags, deletes) are tested on their own in `shows/tests/test_models.py` and `accounts/tests/test_models.py`. `shows/tests/test_admin.py` checks that every model's admin pages load.

Each screen also has a `*_clickthrough.py` test that uses the Django test client. It follows every link, sends HTMX requests, and checks that every control and button has an accessible name.

### Browser checks

Some things the Django test client can't see: layout at 375px and 1280px, the Leaflet map, and live HTMX swaps. Those are checked in a headless browser using the `webapp-testing` skill's server helper:

```bash
.venv/bin/playwright install chromium    # first time only
.venv/bin/python .claude/skills/webapp-testing/scripts/with_server.py \
  --server "exec $PWD/.venv/bin/python $PWD/manage.py runserver 127.0.0.1:8765 --noreload" --port 8765 \
  -- .venv/bin/python scripts/browser_check.py      # or name screens: profile search diary detail edit onboarding
```

- Each screen fails the check if the page scrolls sideways or the console logs an error.
- Screenshots go to [docs/screens/](docs/screens/).
- The script reseeds the demo before each logged-in check.
- Use absolute paths and `exec` in `--server`, as shown above. With relative paths the helper never sees the server come up.

## Screens

| # | Screen | URL | Stories |
| --- | --- | --- | --- |
| 1 | Sign up, log in and onboarding | `/accounts/signup/`, `/accounts/login/`, `/onboarding/` | US-1 |
| 2 | Profile: header, stats, Top 3 and map | `/u/<username>/` (Top 3 editor at `/top3/`) | US-2, US-9, US-10 |
| 3 | Search and log | `/search/`, manual add at `/shows/new/` | US-3, US-4, US-5 |
| 4 | Diary | `/u/<username>/diary/` | US-6 |
| 5 | Show detail, rate and review | `/shows/<id>/` | US-7 |
| 6 | Edit or delete | `/entries/<id>/edit/` | US-8 |

All six are reachable from the main nav: Profile, Diary, Log a show, and Settings. On mobile they're under the Menu button.

## Acceptance criteria

Of the 35 criteria for US-1 to US-10:

- **34 pass**
- **1 needs manual timing** (US-4 median time)

A full Google sign-in with real credentials still needs one manual check. The tests cover the button and the redirect to Google.

"Pass" means an automated test covers the criterion. A name in brackets means the criterion is also confirmed in the browser check for that screen.

| Story | Criterion | Status | Evidence |
| --- | --- | --- | --- |
| US-1 | Sign-up supports email + password and Google OAuth | Pass | `test_us1_signup`: email + password, and the Google button posts to Google with the client ID from `.env`. |
| US-1 | After sign-up I land on onboarding that prompts my first log | Pass | `test_us1_signup` (onboarding) |
| US-1 | Username required, unique and used in /u/username | Pass | `test_us1_signup` |
| US-2 | Profile shows avatar, display name, bio, home city, joined date | Pass | `test_us2_profile` (profile) |
| US-2 | Stats show shows, artists, venues, cities; update on log or delete | Pass | `test_us2_profile`, `test_edit_clickthrough` (edit) |
| US-2 | A logged-out visitor can view a public profile | Pass | `test_us2_profile` (profile) |
| US-2 | I can set my profile to private | Pass | `test_us2_profile` |
| US-3 | Typing an artist name returns matching events, newest first | Pass | `test_us3_search` (search) |
| US-3 | Year, venue and city filters narrow the results | Pass | `test_us3_search` |
| US-3 | Each result shows artist, date, venue and city | Pass | `test_us3_search` |
| US-3 | Results load in under 2 seconds for cached artists | Pass (mock) | `test_us3_search`: a timed cache hit, with no second fetch. Re-check against the live API. |
| US-4 | Tapping Log adds the show and confirms it on screen | Pass | `test_us4_log` (search) |
| US-4 | Logging the same event twice is blocked with a message | Pass | `test_us4_log` (409) |
| US-4 | The venue appears as a pin on my map without a page reload | Pass | `test_us4_log` (HX-Trigger), browser `search` (pin count changes, no reload) |
| US-4 | Median time from search to logged show is under 10 seconds | Manual | Needs timing in the usability test. The PRD's success metric says 20 seconds; reconcile the two. |
| US-5 | Manual form requires artist, date, venue; city required for the map | Pass | `test_us5_manual` |
| US-5 | Manual shows are marked "user-added" and appear in stats and map | Pass | `test_us5_manual`, `test_us6_diary` |
| US-6 | Diary lists every show, newest first, with rating and review snippet | Pass | `test_us6_diary` (diary) |
| US-6 | I can sort by date or rating and filter by year | Pass | `test_us6_diary` (diary) |
| US-7 | Half-star steps from 0.5 to 5; rating is optional | Pass | `test_us7_rate_review` (detail) |
| US-7 | Review is optional and up to 5,000 characters | Pass | `test_us7_rate_review` |
| US-7 | Rating and review can be added at log time or later | Pass | `test_us7_rate_review`, `test_us5_manual` |
| US-7 | My review shows on my diary entry and the show's detail page | Pass | `test_us7_rate_review` |
| US-8 | I can edit the rating and review of any show I logged | Pass | `test_us8_edit_delete` (edit) |
| US-8 | Edited reviews show an "edited" label with the date | Pass | `test_us8_edit_delete` (edit) |
| US-8 | Delete asks for confirmation, then removes from diary, stats, map, Top 3 | Pass | `test_us8_edit_delete` (edit) |
| US-8 | Only the author can edit or delete their own entries | Pass | `test_us8_edit_delete` |
| US-9 | I can choose up to 3 shows from my logged shows only | Pass | `test_us9_top3` |
| US-9 | I can reorder them by drag-and-drop or up/down controls | Pass | `test_us9_top3`: up/down controls. Drag-and-drop isn't built; the criterion allows either. |
| US-9 | Top 3 appears at the top of my profile with artist, date and venue | Pass | `test_us9_top3` (profile) |
| US-9 | Removing a show from my diary removes it from Top 3 | Pass | `test_us9_top3`, browser `edit` (No. 2 moves up to No. 1) |
| US-10 | Each venue shows one pin; multiple visits show a count | Pass | `test_us10_map` (profile) |
| US-10 | Clicking a pin lists the shows there, with date and artist | Pass | `test_us10_map` (profile popup) |
| US-10 | The map opens zoomed to fit all my pins | Pass | `test_us10_map` (bounds), browser `profile` (all pins inside the map) |
| US-10 | Shows without coordinates are listed under "Not on the map" with a fix-location option | Pass | `test_us10_map` |

**US-11 (moderation)** isn't one of the six screens. Its groundwork is in place:

- the `Report` model
- a `review_hidden` field
- Django admin actions to hide a reported review or dismiss the report
- hidden reviews stay visible only to their author

There's no report button and no US-11 tests yet.

## Decisions made for the prototype

- **Private profiles** are visible to their owner only. Everyone else gets a "This profile is private" page, and the diary and map JSON return 403.
- **The spoiler flag and tags are in the data model only.** `Attendance.review_has_spoilers` and the `Tag` model exist, but there's no UI for them yet. The 8 premade tags from the design are seeded by a migration. Custom tags are max 24 characters and unique per user, and nobody can attach another user's custom tag.
- **The search page has a mini "Your map"**, so you can see a pin arrive as you log (US-4).
- **Google sign-ups choose their own username** on a final step before onboarding, rather than getting one made from their email.
- **The log URL uses the setlist.fm id** (`/shows/log/<setlist_id>/`). An event is cached in the database the first time anyone logs it.
- **"Fix location"** is offered only on venues you added yourself. You can enter a city (geocoded) or exact coordinates.
- **Additions to the PRD data model:**
  - `Attendance.review_edited_at`, because `updated_at` also changes when the Top 3 changes
  - `Attendance.review_hidden` (US-11)
  - `Event.created_by` and `Venue.created_by`, for user-added shows
  - `Attendance.review_has_spoilers` and the `tags` table (both now also in PRD.md)

## Mock data

- **[fixtures/demo_shows.json](fixtures/demo_shows.json):** 25 setlists in setlist.fm's response format, across 9 cities in 3 countries. It also holds the lookup tables the mock geocoder uses in place of Mapbox. Dates and tours are illustrative, not real setlists.
- **[services/setlistfm.py](services/setlistfm.py):** the only module that talks to setlist.fm.
  - `MockSetlistClient` answers searches from the fixture.
  - `RealSetlistClient` is a stub that already sends the `x-api-key` header.
  - Set `SETLISTFM_CLIENT=real` in `.env` to switch once it's built.

## Known issues and follow-ups

- At world zoom, pins in the same metro area overlap (the two London venues; Madison Square Garden and Brooklyn Steel), so you have to zoom in to open one. Marker clustering would fix this.
- On phones, a popup on the search page's mini-map can be clipped at the top edge.
- Tailwind runs from the CDN, which is fine for a prototype. Switch to the Tailwind CLI before production.
- Password reset and the other allauth pages work and use the app layout, but their forms aren't custom-styled.
