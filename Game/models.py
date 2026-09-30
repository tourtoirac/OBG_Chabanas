import uuid

from django.db import models

class Game(models.Model):
    key = models.UUIDField(null=False, blank=False, editable=False, unique=True, default=uuid.uuid1)
    name = models.CharField(max_length=64, null=False, blank=False, unique=True)
    min_players = models.IntegerField(null=False, blank=False, default=0)
    max_players = models.IntegerField(null=False, blank=False, default=2)
    max_watchers = models.IntegerField(null=False, blank=False, default=10)
    max_sessions = models.IntegerField(null=False, blank=False, default=10)
    game_json = models.JSONField(null=False, blank=False, default=dict)
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

    def __str__(self):
        return f"{self.name}"

class Variant(models.Model):
    key = models.UUIDField(null=False, blank=False, editable=False, unique=True, default=uuid.uuid1)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    name = models.CharField(max_length=64, null=False, blank=False, unique=False)
    min_players = models.IntegerField(null=False, blank=False, default=0)
    max_players = models.IntegerField(null=False, blank=False, default=2)
    max_watchers = models.IntegerField(null=False, blank=False, default=10)
    game_json = models.JSONField(null=False, blank=False, default=dict)
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

    def __str__(self):
        return f"{self.name}"
