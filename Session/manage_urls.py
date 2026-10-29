from django.urls import path

from Session import manage

# the administration of OBG, mounted under manage/ (Chabanas/urls.py)
urlpatterns = [
    path("", manage.manage_page, name="manage_page"),
    path("api/games", manage.manage_games, name="manage_games"),
    path("api/sessions", manage.manage_sessions, name="manage_sessions"),
    path("api/archive", manage.manage_archive, name="manage_archive"),
    path("api/delete", manage.manage_delete, name="manage_delete"),
    path("api/access", manage.manage_access, name="manage_access"),
    # the refereed games (the modules of Hautefort), turned on or off
    path("refereed/", manage.manage_refereed_page, name="manage_refereed_page"),
    path("api/modules", manage.manage_modules, name="manage_modules"),
    path("api/module", manage.manage_module_active, name="manage_module_active"),
    # a refereed game in prototyping: its key, empty for a public game
    path("api/module_prototype", manage.manage_module_prototype, name="manage_module_prototype"),
    # the documents (rules, charts...) of a refereed game
    path("api/module_documents", manage.manage_module_documents, name="manage_module_documents"),
]
