import uuid

from django.db import models
from Game.models import Game

class Session(models.Model):
    key = models.UUIDField(null=False, blank=False, editable=False, unique=True, default=uuid.uuid1)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    code = models.CharField(max_length=64, blank=True, unique=False, default='')
    variant_name = models.CharField(max_length=64, null=False, blank=False, unique=False, default='default')
    min_players = models.IntegerField(null=False, blank=False, default=0)
    max_players = models.IntegerField(null=False, blank=False, default=2)
    max_watchers = models.IntegerField(null=False, blank=False, default=10)
    allows_watchers = models.BooleanField(null=False, blank=False, default=True)
    access_key = models.CharField(max_length=64, blank=True, unique=False, default='')
    game_json = models.JSONField(null=False, blank=False, default=dict)
    active = models.BooleanField(null=False, blank=False, default=True)
    started = models.BooleanField(null=False, blank=False, default=False)
    # last time a player launched the game; an active session left alone for
    # too long is archived (Session/tools.py cleanup_sessions)
    launched_at = models.DateTimeField(null=True, blank=True)
    # when the session was archived; an archive kept too long is deleted
    archived_at = models.DateTimeField(null=True, blank=True)
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


class ReservedCode(models.Model):
    """
    A code handed out to another OBG service (Hautefort, Air Force): Chabanas
    gives every code of the platform, so no session takes it until it is released.
    """
    code = models.CharField(max_length=64, null=False, blank=False, unique=True)
    # the service holding the code, e.g. "hautefort"
    owner = models.CharField(max_length=32, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()

    class Meta:
        db_table = 'reserved_code'

    def __str__(self):
        return f"{self.owner} - {self.code}"


class OccupiedGame(models.Model):
    """
    A game of the platform with at least one player in it, whatever the service
    playing it (Tourtoirac for the sessions of Chabanas, Hautefort...): the
    services hold the live connections and tell Chabanas, which counts them
    against PARAMS_EXT["MAX_ACTIVE_SESSIONS"].
    """
    # the code of an active session, or a code reserved by another service
    code = models.CharField(max_length=64, null=False, blank=False, unique=True)
    # the service holding the players, e.g. "tourtoirac" or "hautefort"
    service = models.CharField(max_length=32, null=False, blank=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager()

    class Meta:
        db_table = 'occupied_game'

    def __str__(self):
        return f"{self.service} - {self.code}"


class Player(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    nickname = models.CharField(max_length=64, null=False, blank=False, unique=False)
    key = models.CharField(max_length=64, null=True, blank=True, unique=False, default = '')
    # the side this player took among the nationalities of the game; empty when
    # the game declares none
    nationality = models.CharField(max_length=64, null=False, blank=True, unique=False, default='')
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
