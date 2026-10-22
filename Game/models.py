import uuid

from django.db import models

class GameType(models.TextChoices):
    BOARDGAME = "Boardgame", "Boardgame"
    WARGAME = "Wargame", "Wargame"


class Game(models.Model):
    key = models.UUIDField(null=False, blank=False, editable=False, unique=True, default=uuid.uuid1)
    name = models.CharField(max_length=64, null=False, blank=False, unique=True)
    # the readable name the lobby shows; empty: the lobby shows the name
    display_name = models.CharField(max_length=128, null=False, blank=True, default="")
    # the family the lobby files the game under, one tab per type
    game_type = models.CharField(
        max_length=16, null=False, blank=False, choices=GameType.choices, default=GameType.WARGAME
    )
    min_players = models.IntegerField(null=False, blank=False, default=0)
    max_players = models.IntegerField(null=False, blank=False, default=2)
    max_watchers = models.IntegerField(null=False, blank=False, default=10)
    game_json = models.JSONField(null=False, blank=False, default=dict)
    # replaces the "options" block of game_json when a session is created
    options = models.JSONField(null=False, blank=True, default=dict)
    active = models.BooleanField(null=False, blank=False, default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        db_table = 'game'
        indexes = (
            models.Index(fields=["key"]),
            models.Index(fields=["name"]),
            models.Index(fields=["active"]),
        )

    def clean(self):
        # a form field left empty comes back as None: the column is not nullable
        if self.options is None:
            self.options = {}

    def __str__(self):
        return f"{self.name}"

class Variant(models.Model):
    key = models.UUIDField(null=False, blank=False, editable=False, unique=True, default=uuid.uuid1)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    name = models.CharField(max_length=64, null=False, blank=False, unique=False)
    # the readable name the lobby shows; empty: the lobby shows the name
    display_name = models.CharField(max_length=128, null=False, blank=True, default="")
    min_players = models.IntegerField(null=False, blank=False, default=0)
    max_players = models.IntegerField(null=False, blank=False, default=2)
    max_watchers = models.IntegerField(null=False, blank=False, default=10)
    game_json = models.JSONField(null=False, blank=False, default=dict)
    # replaces the "options" block of game_json when a session is created
    options = models.JSONField(null=False, blank=True, default=dict)
    active = models.BooleanField(null=False, blank=False, default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        db_table = 'game_variant'
        indexes = (
            models.Index(fields=["key"]),
            models.Index(fields=["name"]),
        )

    def clean(self):
        # a form field left empty comes back as None: the column is not nullable
        if self.options is None:
            self.options = {}

    def __str__(self):
        return f"{self.name}"
