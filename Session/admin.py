from django.contrib import admin

from Session.models import Session, Player
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
        "locked",
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
    )
    list_filter = (
        "game",
    )
    inlines = [PlayerInLine]

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

