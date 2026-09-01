from django.contrib import admin

from Game.models import Game, Session


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    fields = (
        'key',
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


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    fields = (
        'key',
        'game',
        'code',
        'player1_nickname',
        'player1_key',
        'player2_nickname',
        'player2_key',
        "game_json",
        "active",
    )
    readonly_fields = (
        "key",
    )
    list_display = (
        "game",
        "code",
    )
    search_fields = (
        "code",
        "player1_nickname",
        "player1_key",
        "player2_nickname",
        "player2_key",
    )
    list_filter = (
        "game",
    )
