from django.contrib import admin

from .models import Artist, Attendance, Event, Report, Venue


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


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ["user", "event", "rating", "top3_rank", "review_hidden", "updated_at"]
    list_filter = ["review_hidden"]
    search_fields = ["user__username", "event__artist__name", "review"]
    raw_id_fields = ["event"]


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
