from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.access import visible_owner

from . import top3
from .models import Attendance


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


search = search_results = log_show = add_manual = detail = rate = review = edit = delete = _coming_soon
