from django.urls import path

from Game import proto_views

# the pages of the developers of prototypes, mounted under proto/ (Chabanas/urls.py)
urlpatterns = [
    path("", proto_views.proto_home, name="proto_home"),
    path("login/", proto_views.ProtoLoginView.as_view(), name="proto_login"),
    path("logout/", proto_views.ProtoLogoutView.as_view(), name="proto_logout"),
    path("<uuid:key>/game_json", proto_views.proto_game_json, name="proto_game_json"),
    path("<uuid:key>/game_json.json", proto_views.proto_game_json_download, name="proto_game_json_download"),
    path("<uuid:key>/documents", proto_views.proto_documents, name="proto_documents"),
    path("<uuid:key>/archive", proto_views.proto_archive, name="proto_archive"),
    path("<uuid:key>/prototype_key", proto_views.proto_key, name="proto_key"),
]
