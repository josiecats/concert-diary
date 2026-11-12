from django import forms
from django.contrib import admin

from .models import Artist, Attendance, Event, Report, Tag, Venue


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    search_fields = ["name", "mbid"]


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "country", "lat", "lng"]
    search_fields = ["name", "city"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["artist", "venue", "event_date", "source"]
    list_filter = ["source"]
    search_fields = ["artist__name", "venue__name"]
    autocomplete_fields = ["artist", "venue"]


class AttendanceAdminForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        user, tags = cleaned.get("user"), cleaned.get("tags")
        if user and tags:
            foreign = [t.name for t in tags if t.owner_id and t.owner_id != user.pk]
            if foreign:
                self.add_error("tags", f"These are another user's custom tags: {', '.join(foreign)}.")
        return cleaned


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    form = AttendanceAdminForm
    list_display = ["user", "event", "rating", "top3_rank", "review_has_spoilers", "review_hidden", "updated_at"]
    list_filter = ["review_hidden", "review_has_spoilers"]
    search_fields = ["user__username", "event__artist__name", "review"]
    raw_id_fields = ["event"]
    filter_horizontal = ["tags"]


class TagTypeFilter(admin.SimpleListFilter):
    title = "type"
    parameter_name = "type"

    def lookups(self, request, model_admin):
        return [("premade", "Premade"), ("custom", "Custom")]

    def queryset(self, request, queryset):
        if self.value() == "premade":
            return queryset.filter(owner__isnull=True)
        if self.value() == "custom":
            return queryset.filter(owner__isnull=False)
        return queryset


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "is_premade"]
    list_filter = [TagTypeFilter]
    search_fields = ["name", "owner__username"]
    raw_id_fields = ["owner"]

    @admin.display(boolean=True, description="Premade")
    def is_premade(self, obj):
        return obj.is_premade


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """Moderation queue (US-11)."""

    list_display = ["attendance", "reporter", "reason", "status", "created_at"]
    list_filter = ["status"]
    actions = ["hide_review", "dismiss"]

    @admin.action(description="Hide the reported review")
    def hide_review(self, request, queryset):
        for report in queryset.select_related("attendance"):
            report.attendance.review_hidden = True
            report.attendance.save(update_fields=["review_hidden"])
        queryset.update(status=Report.STATUS_HIDDEN)

    @admin.action(description="Dismiss report")
    def dismiss(self, request, queryset):
        queryset.update(status=Report.STATUS_DISMISSED)
