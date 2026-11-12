from django.urls import path

from . import views

app_name = "maps"

urlpatterns = [
    path("u/<str:username>/venues.json", views.venues_json, name="venues"),
    path("venues/<int:pk>/fix-location/", views.fix_location, name="fix_location"),
]
