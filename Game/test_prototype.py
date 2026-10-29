import json

from django.test import TestCase
from django.urls import reverse

from Game.models import Game
from Game.tools import return_game_json
from Session.models import Player, Session


class PrototypeTests(TestCase):
    """A game in prototyping: listed locked, created and joined with its key only."""

    def setUp(self):
        self.game = Game.objects.create(name="proto", game_json={"game": "proto"}, prototype_key="s3cret")
        self.public = Game.objects.create(name="public", game_json={"game": "public"})
        self.session = Session.objects.create(game=self.game, code="PROTO001", max_players=3)
        Player.objects.create(session=self.session, nickname="Alice", key="k", owner=True)

    def post(self, url_name, data):
        return self.client.post(reverse(url_name), json.dumps(data), content_type="application/json")

    def test_the_lobby_knows_a_game_is_private_but_not_its_key(self):
        data = return_game_json(self.game)
        self.assertTrue(data["private"])
        self.assertNotIn("s3cret", json.dumps(data, default=str))
        self.assertFalse(return_game_json(self.public)["private"])

    def test_unlock(self):
        self.assertEqual(self.post("game_unlock", {"game_name": "proto", "prototype_key": "s3cret"}).status_code, 200)
        self.assertEqual(self.post("game_unlock", {"game_name": "proto", "prototype_key": "nope"}).status_code, 423)
        self.assertEqual(self.post("game_unlock", {"game_name": "proto", "prototype_key": 1}).status_code, 423)
        self.assertEqual(self.post("game_unlock", {"game_name": "public", "prototype_key": ""}).status_code, 200)
        self.assertEqual(self.post("game_unlock", {"game_name": "none", "prototype_key": ""}).status_code, 404)

    def test_create_needs_the_key(self):
        body = {"game_name": "proto", "nickname": "Bob"}
        self.assertEqual(self.post("session_create", body).status_code, 423)
        self.assertEqual(self.post("session_create", {**body, "prototype_key": "nope"}).status_code, 423)
        self.assertEqual(self.post("session_create", {**body, "prototype_key": "s3cret"}).status_code, 201)
        # a public game asks for nothing
        self.assertEqual(self.post("session_create", {"game_name": "public", "nickname": "Bob"}).status_code, 201)

    def test_join_needs_the_key_for_players_and_watchers(self):
        for role in ("player", "watcher"):
            body = {"session_code": "PROTO001", "nickname": f"Bob-{role}", "role": role}
            self.assertEqual(self.post("session_join", body).status_code, 423)
            self.assertEqual(self.post("session_join", {**body, "prototype_key": "s3cret"}).status_code, 200)
        # even a returning seat, when it comes back through the lobby
        body = {"session_code": "PROTO001", "nickname": "Alice", "key": "k"}
        self.assertEqual(self.post("session_join", body).status_code, 423)
        self.assertEqual(self.post("session_join", {**body, "prototype_key": "s3cret"}).status_code, 200)
