from django.contrib import admin
from django.db import models

from Game.models import Game, Variant
from Game.widgets import PrettyJSONWidget

class VariantInLine(admin.TabularInline):
    model = Variant
    fk_name = "game"
    extra = 0
    fields = (
        "name",
        "display_name",
        "max_players",
        "max_watchers",
        "active",
    )


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    fields = (
        'key',
        'name',
        'display_name',
        'game_type',
        'min_players',
        'max_players',
        'max_watchers',
        'max_sessions',
        "game_json",
        "options",
        "active",
    )
    readonly_fields = (
        "key",
    )
    list_display = (
        "name",
        "display_name",
        "game_type",
        "active",
        "max_players",
        "max_watchers",
    )
    search_fields = (
        "name",
        "display_name",
    )
    list_filter = (
        'game_type',
        'active',
    )
    inlines = [VariantInLine]
    # le game_json passe par le widget lisible de tous les champs JSON
    formfield_overrides = {
        models.JSONField: {"widget": PrettyJSONWidget},
    }


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    fields = (
        'key',
        'game',
        'name',
        'display_name',
        'min_players',
        'max_players',
        'max_watchers',
        "game_json",
        "options",
        "active",
    )
    readonly_fields = (
        "key",
    )
    list_display = (
        "name",
        "display_name",
        "game",
        "active"
    )
    search_fields = (
        "name",
        "display_name",
    )
    list_filter = (
        "game",
        "active"
    )
    formfield_overrides = {
        models.JSONField: {"widget": PrettyJSONWidget},
    }
