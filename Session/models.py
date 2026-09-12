import uuid

from django.db import models
from Game.models import Game

class Session(models.Model):
    key = models.UUIDField(null=False, blank=False, editable=False, unique=True, default=uuid.uuid1)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    code = models.CharField(max_length=64, blank=True, unique=False, default='')
    variant_name = models.CharField(max_length=64, null=False, blank=False, unique=False, default='default')
    max_players = models.IntegerField(null=False, blank=False, default=2)
    max_watchers = models.IntegerField(null=False, blank=False, default=10)
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
        return f"{self.game.name} - {self.code}"


class Player(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    nickname = models.CharField(max_length=64, null=False, blank=False, unique=False)
    key = models.CharField(max_length=64, null=True, blank=True, unique=False, default = '')
    owner = models.BooleanField(null=False, blank=False, default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        db_table = 'session_players'
        indexes = (
            models.Index(fields=["key"]),
            models.Index(fields=["nickname"]),
        )

    def __str__(self):
        return f"{self.session.game.name} - {self.nickname}"
