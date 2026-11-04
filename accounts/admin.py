from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "display_name", "home_city", "is_private", "created_at"]
    list_filter = ["is_private"]
    search_fields = ["user__username", "display_name"]
