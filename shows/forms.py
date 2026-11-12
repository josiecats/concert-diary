from datetime import date
from decimal import Decimal

from django import forms

from .models import RATING_CHOICES, REVIEW_MAX_LENGTH, Attendance

FIRST_YEAR = 1960


def year_choices():
    return [("", "Any year")] + [(str(y), str(y)) for y in range(date.today().year, FIRST_YEAR - 1, -1)]


def rating_choices():
    return [("", "No rating")] + [(f"{r}", f"{r:g} stars" if r != 1 else "1 star") for r in RATING_CHOICES]


class SearchForm(forms.Form):
    artist = forms.CharField(
        max_length=120, required=False, label="Artist",
        widget=forms.SearchInput(attrs={
            "class": "field search-hero", "placeholder": "Artist name, e.g. Phoebe Bridgers", "autocomplete": "off", "autofocus": True,
        }),
    )
    year = forms.TypedChoiceField(choices=year_choices, required=False, coerce=int, empty_value=None,
                                  widget=forms.Select(attrs={"class": "field h-full py-3.5"}))
    venue = forms.CharField(max_length=120, required=False,
                            widget=forms.TextInput(attrs={"class": "field", "placeholder": "Any venue"}))
    city = forms.CharField(max_length=120, required=False,
                           widget=forms.TextInput(attrs={"class": "field", "placeholder": "Any city"}))


class RatingReviewFields(forms.Form):
    """Optional rating and review, shared by manual entry and editing (US-7)."""

    rating = forms.TypedChoiceField(
        choices=rating_choices, required=False, coerce=Decimal, empty_value=None,
        widget=forms.Select(attrs={"class": "field"}),
    )
    review = forms.CharField(
        required=False, max_length=REVIEW_MAX_LENGTH,
        widget=forms.Textarea(attrs={"class": "field", "rows": 5, "maxlength": REVIEW_MAX_LENGTH,
                                     "placeholder": "What do you want to remember?"}),
    )


class ManualShowForm(RatingReviewFields):
    artist = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "field"}))
    event_date = forms.DateField(label="Date", widget=forms.DateInput(attrs={"class": "field", "type": "date"}))
    venue_name = forms.CharField(label="Venue", max_length=200, widget=forms.TextInput(attrs={"class": "field"}))
    city = forms.CharField(
        max_length=120, error_messages={"required": "City is needed to place the show on your map."},
        widget=forms.TextInput(attrs={"class": "field"}),
    )
    country = forms.CharField(max_length=120, required=False, widget=forms.TextInput(attrs={"class": "field"}))
    tour_name = forms.CharField(label="Tour or event name", max_length=200, required=False,
                                widget=forms.TextInput(attrs={"class": "field"}))

    field_order = ["artist", "event_date", "venue_name", "city", "country", "tour_name", "rating", "review"]

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_event_date(self):
        value = self.cleaned_data["event_date"]
        if value > date.today():
            raise forms.ValidationError("The date can't be in the future. Log shows after you've been.")
        return value

    def clean(self):
        data = super().clean()
        if self.user and all(data.get(k) for k in ("artist", "event_date", "venue_name", "city")):
            exists = Attendance.objects.filter(
                user=self.user,
                event__artist__name__iexact=data["artist"].strip(),
                event__venue__name__iexact=data["venue_name"].strip(),
                event__venue__city__iexact=data["city"].strip(),
                event__event_date=data["event_date"],
            ).exists()
            if exists:
                raise forms.ValidationError("This show is already in your diary.")
        return data


class EntryForm(RatingReviewFields):
    """Edit a logged show's rating and review (US-8)."""

