from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("u/<str:username>/", views.profile, name="profile"),
    path("settings/profile/", views.settings_view, name="settings"),
    path("onboarding/", views.onboarding, name="onboarding"),
]
