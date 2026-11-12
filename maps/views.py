from collections import OrderedDict

from django import forms
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.access import visible_owner
from services import geocoding
from shows.models import Attendance, Venue


def venue_pins(owner):
    """One pin per venue with coordinates; each lists the shows seen there (US-10)."""
    logs = (
        Attendance.objects.with_related()
        .filter(user=owner, event__venue__lat__isnull=False, event__venue__lng__isnull=False)
        .order_by("-event__event_date")
    )
    pins = OrderedDict()
    for att in logs:
        venue = att.event.venue
        pin = pins.setdefault(venue.pk, {
            "venue_id": venue.pk, "name": venue.name, "city": venue.city, "country": venue.country,
            "lat": venue.lat, "lng": venue.lng, "count": 0, "shows": [],
        })
        pin["count"] += 1
        pin["shows"].append({
            "artist": att.event.artist.name,
            "date": f"{att.event.event_date:%b} {att.event.event_date.day}, {att.event.event_date.year}",
            "url": reverse("shows:detail", args=[att.event_id]),
        })
    return list(pins.values())


def venues_json(request, username):
    owner, denied = visible_owner(request, username)
    if denied:
        return JsonResponse({"error": "This profile is private."}, status=403)
    pins = venue_pins(owner)
    bounds = None
    if pins:
        lats, lngs = [p["lat"] for p in pins], [p["lng"] for p in pins]
        bounds = [[min(lats), min(lngs)], [max(lats), max(lngs)]]
    unmapped = Attendance.objects.filter(user=owner, event__venue__lat__isnull=True).count()
    return JsonResponse({"pins": pins, "bounds": bounds, "unmapped": unmapped})


class FixLocationForm(forms.Form):
    city = forms.CharField(max_length=120, widget=forms.TextInput(attrs={"class": "field"}))
    lat = forms.FloatField(required=False, min_value=-90, max_value=90, label="Latitude",
                           widget=forms.NumberInput(attrs={"class": "field", "step": "any", "placeholder": "42.4406"}))
    lng = forms.FloatField(required=False, min_value=-180, max_value=180, label="Longitude",
                           widget=forms.NumberInput(attrs={"class": "field", "step": "any", "placeholder": "-76.4966"}))

    def __init__(self, *args, venue=None, **kwargs):
        self.venue = venue
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        lat, lng = data.get("lat"), data.get("lng")
        if (lat is None) != (lng is None):
            raise forms.ValidationError("Enter both latitude and longitude, or leave both blank.")
        if lat is None and data.get("city"):
            coords = geocoding.geocode(self.venue.name, data["city"])
            if coords is None:
                raise forms.ValidationError(
                    "We couldn't find that city. Check the spelling or enter coordinates."
                )
            data["lat"], data["lng"] = coords
        return data


@login_required
def fix_location(request, pk):
    """Place a user-added venue on the map. Only its creator can do this."""
    venue = get_object_or_404(
        Venue.objects.filter(events__attendances__user=request.user).distinct(), pk=pk, created_by=request.user
    )
    htmx = request.headers.get("HX-Request") == "true"
    form = FixLocationForm(request.POST or None, venue=venue, initial={"city": venue.city})
    if request.method == "POST":
        if form.is_valid():
            venue.city = form.cleaned_data["city"]
            venue.lat, venue.lng = form.cleaned_data["lat"], form.cleaned_data["lng"]
            venue.save(update_fields=["city", "lat", "lng"])
            if not htmx:
                return redirect("accounts:profile", request.user.username)
            resp = render(request, "maps/partials/location_fixed.html", {"venue": venue})
            resp["HX-Trigger"] = "map-changed"
            return resp
        status = 422
    else:
        status = 200
    template = "maps/partials/fix_location_form.html" if htmx else "maps/fix_location.html"
    return render(request, template, {"form": form, "venue": venue}, status=status)
