import uuid

from django.db import models


class Waterloo(models.Model):
    waterloo_key = models.UUIDField(null=False, blank=False, editable=False, unique=True, default=uuid.uuid1)
    waterloo_code = models.CharField(max_length=12, null=False, blank=False, unique=True)
    player1_nickname = models.CharField(max_length=64, null=False, blank=False, unique=False)
    player1_key = models.CharField(max_length=64, null=False, blank=True, default='')
    player2_nickname = models.CharField(max_length=64, blank=True, default= '', unique=False)
    player2_key = models.CharField(max_length=64, null=False, blank=True, default='')
    game_json = models.JSONField(null=False, blank=False, default=dict)
    active = models.BooleanField(null=False, blank=False, default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        db_table = 'waterloo'
        indexes = (
            models.Index(fields=["waterloo_key"]),
            models.Index(fields=["waterloo_code"]),
        )

    def __str__(self):
        return f"{self.created_at} : {self.waterloo_code} - {self.player1_nickname} vs {self.player2_nickname}"
