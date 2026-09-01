import uuid

from django.db import models

class Game(models.Model):
    key = models.UUIDField(null=False, blank=False, editable=False, unique=True, default=uuid.uuid1)
    name = models.CharField(max_length=64, null=False, blank=False, unique=True)
    max_players = models.IntegerField(null=False, blank=False, default=2)
    max_watchers = models.IntegerField(null=False, blank=False, default=10)
    game_json = models.JSONField(null=False, blank=False, default=dict)
    active = models.BooleanField(null=False, blank=False, default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        db_table = 'game'
        indexes = (
            models.Index(fields=["key"]),
        )

    def __str__(self):
        return f"{self.name}"


class Session(models.Model):
    key = models.UUIDField(null=False, blank=False, editable=False, unique=True, default=uuid.uuid1)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    code = models.CharField(max_length=64, blank=True, unique=True, default='')
    player1_nickname = models.CharField(max_length=64, null=False, blank=False, unique=False)
    player1_key = models.CharField(max_length=64, null=False, blank=True, default='')
    player2_nickname = models.CharField(max_length=64, blank=True, default='', unique=False)
    player2_key = models.CharField(max_length=64, null=False, blank=True, default='')
    game_json = models.JSONField(null=False, blank=False, default=dict)
    active = models.BooleanField(null=False, blank=False, default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        db_table = 'session'
        indexes = (
            models.Index(fields=["key"]),
            models.Index(fields=["game"]),
            models.Index(fields=["code"]),
            models.Index(fields=["active"]),
        )

    def __str__(self):
        return f"{self.game.name} - {self.key} - {self.player1_nickname} vs {self.player2_nickname}"
