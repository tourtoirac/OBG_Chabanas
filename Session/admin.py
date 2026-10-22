from django.contrib import admin
from django.db import models

from Game.widgets import PrettyJSONWidget
from Session.models import OccupiedGame, ReservedCode, Session, Player
# Register your models here.

class PlayerInLine(admin.TabularInline):
    model = Player
    fk_name = "session"
    extra = 0
    fields = (
        "nickname",
        "owner"
    )

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    fields = (
        'key',
        'game',
        'code',
        'access_key',
        'variant_name',
        'allows_watchers',
        'min_players',
        'max_players',
        'max_watchers',
        "game_json",
        "started",
        "active",
        "launched_at",
        "archived_at",
    )
    readonly_fields = (
        "key",
        "launched_at",
        "archived_at",
    )
    list_display = (
        "game",
        "code",
        "launched_at",
        "archived_at",
    )
    search_fields = (
        "code",
    )
    list_filter = (
        "game",
    )
    inlines = [PlayerInLine]
    formfield_overrides = {
        models.JSONField: {"widget": PrettyJSONWidget},
    }

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    fields = (
        'session',
        'nickname',
        'key',
    )
    list_display = (
        "session",
        "nickname",
        "key",
    )


@admin.register(ReservedCode)
class ReservedCodeAdmin(admin.ModelAdmin):
    fields = (
        'code',
        'owner',
    )
    list_display = (
        "code",
        "owner",
        "created_at",
    )
    search_fields = (
        "code",
    )

@admin.register(OccupiedGame)
class OccupiedGameAdmin(admin.ModelAdmin):
    fields = (
        'code',
        'service',
    )
    list_display = (
        "code",
        "service",
        "created_at",
    )
