from django.contrib import admin

from Waterloo.models import Waterloo


@admin.register(Waterloo)
class WaterlooAdmin(admin.ModelAdmin):
    fields = (
        'waterloo_key',
        'waterloo_code',
        "player1_nickname",
        "player1_key",
        "player2_nickname",
        "player2_key",
        "game_json",
        "active",
    )
    readonly_fields = (
        "waterloo_key",
    )
    list_display = (
        "waterloo_code",
        "player1_nickname",
        "player2_nickname",
    )
    search_fields = (
        "waterloo_code",
        "player1_nickname",
        "player2_nickname",
    )
    list_filter = (
        'active',
    )
