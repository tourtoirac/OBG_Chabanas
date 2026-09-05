from django.contrib import admin

from Game.models import Game, Variant

class VariantInLine(admin.TabularInline):
    model = Variant
    fk_name = "game"
    extra = 0
    fields = (
        "name",
        "max_players",
        "max_watchers",
        "active",
    )


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    fields = (
        'key',
        'name',
        'max_players',
        'max_watchers',
        'max_sessions',
        "game_json",
        "active",
    )
    readonly_fields = (
        "key",
    )
    list_display = (
        "name",
        "active",
        "max_players",
        "max_watchers",
    )
    search_fields = (
        "name",
    )
    list_filter = (
        'active',
    )
    inlines = [VariantInLine]


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    fields = (
        'key',
        'game',
        'name',
        'max_players',
        'max_watchers',
        "game_json",
        "active",
    )
    readonly_fields = (
        "key",
    )
    list_display = (
        "name",
        "game",
        "active"
    )
    search_fields = (
        "name",
    )
    list_filter = (
        "game",
        "active"
    )
