import json

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.access import visible_owner
from services import geocoding, setlistfm

from . import top3
from .forms import ManualShowForm, SearchForm
from .models import Artist, Attendance, Event, Venue


def _is_htmx(request):
    return request.headers.get("HX-Request") == "true"


def _own_attendance(request, pk):
    """Entries are only ever edited by their author; anyone else gets a 404."""
    return get_object_or_404(Attendance.objects.with_related(), pk=pk, user=request.user)


def _coming_soon(request, *args, **kwargs):
    return render(request, "shows/coming_soon.html")


# Screen 2: Top 3 (US-9) -------------------------------------------------------------------

def _top3_editor(request, status=200, error=""):
    logs = Attendance.objects.with_related().filter(user=request.user)
    context = {
        "top3": top3.top3_for(request.user),
        "candidates": logs.filter(top3_rank__isnull=True).order_by("-event__event_date"),
        "error": error,
    }
    template = "shows/partials/top3_editor.html" if _is_htmx(request) else "shows/top3.html"
    return render(request, template, context, status=status)


@login_required
def top3_view(request):
    return _top3_editor(request)


@login_required
@require_POST
def top3_add(request, pk):
    attendance = _own_attendance(request, pk)
    try:
        top3.add(attendance)
    except top3.Top3Full:
        return _top3_editor(request, status=409, error="Your Top 3 is full. Remove a show to make room.")
    return _top3_editor(request) if _is_htmx(request) else redirect("shows:top3")


@login_required
@require_POST
def top3_move(request, pk, direction):
    if direction not in ("up", "down"):
        raise Http404
    top3.move(_own_attendance(request, pk), direction)
    return _top3_editor(request) if _is_htmx(request) else redirect("shows:top3")


@login_required
@require_POST
def top3_remove(request, pk):
    top3.remove(_own_attendance(request, pk))
    return _top3_editor(request) if _is_htmx(request) else redirect("shows:top3")


# Screen 4: Diary (US-6), filled in properly with its screen ------------------------------

def diary(request, username):
    owner, denied = visible_owner(request, username)
    if denied:
        return denied
    return _coming_soon(request)


detail = rate = review = edit = delete = _coming_soon


# Screen 3: search and log (US-3, US-4, US-5) ---------------------------------------------

def _search_context(request):
    form = SearchForm(request.GET or None)
    results, query = [], ""
    if form.is_valid():
        query = form.cleaned_data["artist"].strip()
        results = setlistfm.search(
            query, year=form.cleaned_data["year"],
            venue=form.cleaned_data["venue"], city=form.cleaned_data["city"],
        )
    logged = set(
        Attendance.objects.filter(user=request.user, event__setlistfm_id__in=[r.id for r in results])
        .values_list("event__setlistfm_id", flat=True)
    )
    return {
        "form": form,
        "query": query,
        "results": results,
        "logged_ids": logged,
        "too_short": 0 < len(query) < setlistfm.MIN_QUERY_LENGTH,
        "manual_url": _manual_url(form),
    }


def _manual_url(form):
    from urllib.parse import urlencode

    data = form.cleaned_data if form.is_bound and form.is_valid() else {}
    params = {k: data.get(k) for k in ("artist", "venue", "city") if data.get(k)}
    if "venue" in params:
        params["venue_name"] = params.pop("venue")
    url = reverse("shows:add_manual")
    return f"{url}?{urlencode(params)}" if params else url


@login_required
def search(request):
    context = _search_context(request)
    context["log_count"] = Attendance.objects.filter(user=request.user).count()
    return render(request, "shows/search.html", context)


@login_required
def search_results(request):
    if not _is_htmx(request):
        return redirect(f"{reverse('shows:search')}?{request.GET.urlencode()}")
    return render(request, "shows/partials/results.html", _search_context(request))


@login_required
@require_POST
def log_show(request, setlist_id):
    """One-tap logging from search results (US-4). Caches the event on first log."""
    event = setlistfm.cache_event(setlist_id)
    if event is None:
        raise Http404("No such setlist.")
    # Same shape as a SetlistResult so the partial renders identically in search and here.
    result = {"id": setlist_id, "artist_name": event.artist.name, "venue_name": event.venue.name,
              "event_date": event.event_date}
    context = {"result": result, "event": event}
    try:
        with transaction.atomic():
            attendance = Attendance.objects.create(user=request.user, event=event)
    except IntegrityError:
        context.update(logged=True, duplicate=True)
        return render(request, "shows/partials/log_button.html", context, status=409)

    context.update(logged=True, just_logged=True, attendance=attendance)
    if not _is_htmx(request):
        return redirect("shows:detail", event.pk)
    resp = render(request, "shows/partials/log_button.html", context)
    resp["HX-Trigger"] = json.dumps({"show-logged": {"venue": event.venue.name, "event": event.pk}})
    return resp


def _find_or_create_venue(user, name, city, country):
    venue = Venue.objects.filter(name__iexact=name, city__iexact=city).first()
    if venue:
        return venue
    lat, lng = geocoding.geocode(name, city) or (None, None)
    return Venue.objects.create(name=name, city=city, country=country, lat=lat, lng=lng, created_by=user)


@login_required
def add_manual(request):
    """Manual entry for shows setlist.fm doesn't have (US-5)."""
    initial = {k: request.GET.get(k, "") for k in ("artist", "venue_name", "city")}
    form = ManualShowForm(request.POST or None, user=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            artist = Artist.objects.filter(name__iexact=d["artist"].strip()).first() or Artist.objects.create(
                name=d["artist"].strip()
            )
            venue = _find_or_create_venue(request.user, d["venue_name"].strip(), d["city"].strip(), d["country"].strip())
            event = Event.objects.create(
                artist=artist, venue=venue, event_date=d["event_date"], tour_name=d["tour_name"],
                source=Event.SOURCE_USER, created_by=request.user,
            )
            Attendance.objects.create(user=request.user, event=event, rating=d["rating"], review=d["review"])
        return redirect("shows:detail", event.pk)
    return render(request, "shows/add_manual.html", {"form": form})
