from django.urls import path

from Game import json_api, views

urlpatterns = [
    path("json/get", json_api.get_game_json, name="game_json_get"),
    path("json/update", json_api.update_game_json, name="game_json_update"),
    path("list", views.game_list, name="game_list"),
    path("unlock", views.game_unlock, name="game_unlock"),
]
