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
    readonly_fields = (
        "key",
    )
    list_display = (
        "session",
        "nickname",
        "key",
    )

