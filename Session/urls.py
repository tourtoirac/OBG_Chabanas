from django.urls import path

from Session import views

urlpatterns = [
    path("archive", views.session_archive, name="session_archive"),
    path("create", views.session_create, name="session_create"),
    path("get", views.session_get, name="session_get"),
    path("get_archive", views.session_get_archive, name="session_get_archive"),
    path("join", views.session_join, name="session_join"),
    path("launch", views.session_launch, name="session_launch"),
    path("list", views.session_list, name="session_list"),
    path("occupy", views.session_occupy, name="session_occupy"),
    path("release_code", views.session_release_code, name="session_release_code"),
    path("reserve_code", views.session_reserve_code, name="session_reserve_code"),
    path("sync_occupancy", views.session_sync_occupancy, name="session_sync_occupancy"),
    path("update", views.session_update, name="session_update"),
    path("vacate", views.session_vacate, name="session_vacate"),
]
