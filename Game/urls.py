from django.urls import path

from Game import views

urlpatterns = [
    path("list", views.game_list, name="game_list"),
]
