from django.urls import path

from Waterloo import views

urlpatterns = [
    path("archive", views.waterloo_archive, name="waterloo_archive"),
    path("create", views.waterloo_create, name="waterloo_create"),
    path("get_archive", views.waterloo_get_archive, name="waterloo_get_archive"),
    path("join", views.waterloo_join, name="waterloo_join"),
    path("list", views.waterloo_list, name="waterloo_list"),
    path("update", views.waterloo_update, name="waterloo_update"),
]
