from django.urls import path

from . import views

app_name = "shows"

urlpatterns = [
    # Search and log (US-3, US-4, US-5)
    path("search/", views.search, name="search"),
    path("search/results/", views.search_results, name="search_results"),
    path("shows/log/<str:setlist_id>/", views.log_show, name="log"),
    path("shows/new/", views.add_manual, name="add_manual"),
    # Diary (US-6)
    path("u/<str:username>/diary/", views.diary, name="diary"),
    # Show detail, rate and review (US-7)
    path("shows/<int:event_id>/", views.detail, name="detail"),
    path("entries/<int:pk>/rating/", views.rate, name="rate"),
    path("entries/<int:pk>/review/", views.review, name="review"),
    # Edit and delete (US-8)
    path("entries/<int:pk>/edit/", views.edit, name="edit"),
    path("entries/<int:pk>/delete/", views.delete, name="delete"),
    # Top 3 (US-9)
    path("top3/", views.top3_view, name="top3"),
    path("top3/<int:pk>/add/", views.top3_add, name="top3_add"),
    path("top3/<int:pk>/move/<str:direction>/", views.top3_move, name="top3_move"),
    path("top3/<int:pk>/remove/", views.top3_remove, name="top3_remove"),
]
