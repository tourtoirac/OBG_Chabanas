from django.urls import path

from Session import views

urlpatterns = [
    path("archive", views.session_archive, name="session_archive"),
    path("create", views.session_create, name="session_create"),
    path("get", views.session_get, name="session_get"),
    path("get_archive", views.session_get_archive, name="session_get_archive"),
    path("join", views.session_join, name="session_join"),
    path("list", views.session_list, name="session_list"),
    path("update", views.session_update, name="session_update"),
]
