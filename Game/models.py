import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

def clean_documents_field(row) -> None:
    """Refuses documents that are not a list of {"src": ..., "name": ...}; empty stands for none."""
    if row.documents is None:
        row.documents = []
    documents = row.documents
    if not isinstance(documents, list) or any(
        not isinstance(document, dict) or not isinstance(document.get("src"), str) or not document["src"]
        or not isinstance(document.get("name", ""), str)
        for document in documents
    ):
        raise ValidationError({"documents": 'Une liste de {"src": "...", "name": "..."} est attendue.'})


class GameType(models.TextChoices):
    BOARDGAME = "Boardgame", "Boardgame"
    WARGAME = "Wargame", "Wargame"


class Game(models.Model):
    key = models.UUIDField(null=False, blank=False, editable=False, unique=True, default=uuid.uuid1)
    name = models.CharField(max_length=64, null=False, blank=False, unique=True)
    # the readable name the lobby shows; empty: the lobby shows the name
    display_name = models.CharField(max_length=128, null=False, blank=True, default="")
    # the label of the game tab of the lobby; empty: the display_name
    thumbnail_display = models.CharField(max_length=128, null=False, blank=True, default="")
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
    # the documents (rules, charts...) of the game: [{"src": ..., "name": ...}].
    # Given to a session as the "documents" block of its game_json, and listed
    # by the lobby (the documents of the game only, never those of a variant)
    documents = models.JSONField(null=False, blank=True, default=list)
    active = models.BooleanField(null=False, blank=False, default=True)
    # a game in prototyping: the lobby shows it locked, and only who gives this
    # key may create or join one of its sessions; empty: a public game
    prototype_key = models.CharField(max_length=64, null=False, blank=True, default="")
    # the users who develop this prototype: on the proto/ pages they upload its
    # game_json and the archive of its resources (Game/prototype.py)
    prototype_users = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="prototypes")
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
        clean_documents_field(self)

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
    # the documents (rules, charts...) of the game: [{"src": ..., "name": ...}].
    # Given to a session as the "documents" block of its game_json, and listed
    # by the lobby (the documents of the game only, never those of a variant)
    documents = models.JSONField(null=False, blank=True, default=list)
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
        clean_documents_field(self)

    def __str__(self):
        return f"{self.name}"
