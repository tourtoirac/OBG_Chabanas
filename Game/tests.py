import json

from django.shortcuts import Http404
from django.test import TestCase, RequestFactory
from django.urls import reverse

from Game.models import Game, Variant
from Game.tools import return_game_json
from Game.views import game_list
from Game.widgets import PrettyJSONWidget


class PrettyJSONWidgetTest(TestCase):
    def test_format_value_indents_the_json(self):
        widget = PrettyJSONWidget()
        rendered = widget.format_value('{"b": 2, "a": 1}')
        self.assertEqual(json.loads(rendered), {"b": 2, "a": 1})
        self.assertIn("\n", rendered)

    def test_format_value_keeps_invalid_input_untouched(self):
        widget = PrettyJSONWidget()
        self.assertEqual(widget.format_value("{oops"), "{oops")

    def test_format_value_keeps_an_empty_value(self):
        widget = PrettyJSONWidget()
        self.assertEqual(widget.format_value(""), "")

    def test_media_loads_the_editor_assets(self):
        media = str(PrettyJSONWidget().media)
        self.assertIn("pretty_json.js", media)
        self.assertIn("pretty_json.css", media)


class GameModelTest(TestCase):
    def test_create_game(self):
        game = Game.objects.create(
            name= "Test Game",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "default",
            },
            active=True
        )
        self.assertEqual(game.name, "Test Game")
        self.assertEqual(game.max_players, 2)
        self.assertEqual(game.max_watchers, 10)
        self.assertEqual(game.max_sessions, 5)
        self.assertEqual(game.active, True)
        self.assertEqual(game.game_json, {"game": "default"})
        self.assertEqual(game.__str__(), "Test Game")

    def test_create_variant(self):
        game = Game.objects.create(
            name= "Test Game",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "test",
            },
            active=True
        )
        variant = Variant.objects.create(
            game=game,
            name="Variant Name",
            max_players=3,
            max_watchers=5,
            game_json={
                "game": "variant",
            },
            active=True

        )
        self.assertEqual(variant.name, "Variant Name")
        self.assertEqual(variant.max_players, 3)
        self.assertEqual(variant.max_watchers, 5)
        self.assertTrue(variant.active)
        self.assertEqual(variant.__str__(), "Variant Name")


class ReturnGameJsonTest(TestCase):

    def test_return_game_json_default_variant(self):
        game = Game.objects.create(
            name="waterloo",
            min_players=1,
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={"game": "waterloo"},
            active=True,
        )

        game_data = return_game_json(game)
        self.assertEqual(game_data["key"], game.key)
        self.assertEqual(game_data["name"], "waterloo")
        self.assertEqual(game_data["max_sessions"], 5)
        self.assertEqual(list(game_data["variant"].keys()), ["default"])
        self.assertEqual(game_data["variant"]["default"], {
            "key": game.key,
            "name": "default",
            "min_players": 1,
            "max_players": 2,
            "max_watchers": 10,
        })

    def test_return_game_json_with_active_variant(self):
        game = Game.objects.create(name="waterloo", active=True)
        variant = Variant.objects.create(
            game=game,
            name="solo",
            min_players=1,
            max_players=3,
            max_watchers=15,
            active=True,
        )

        game_data = return_game_json(game)
        self.assertEqual(sorted(game_data["variant"].keys()), ["default", "solo"])
        self.assertEqual(game_data["variant"]["solo"], {
            "key": variant.key,
            "name": "solo",
            "active": True,
            "min_players": 1,
            "max_players": 3,
            "max_watchers": 15,
        })

    def test_return_game_json_ignores_inactive_variant(self):
        game = Game.objects.create(name="waterloo", active=True)
        Variant.objects.create(
            game=game,
            name="archived",
            active=False,
        )

        game_data = return_game_json(game)
        self.assertEqual(list(game_data["variant"].keys()), ["default"])


class GameListTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.waterloo = Game.objects.create(
            name="waterloo",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "waterloo",
            },
            active=True,
        )
        self.diplomacy = Game.objects.create(
            name="diplomacy",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "diplomacy",
            },
            active=True,
        )
        self.diplomacy_variant = Variant.objects.create(
            game=self.diplomacy,
            name="variant",
            max_players=7,
            max_watchers=15,
            game_json={
                "game": "diplomacy variant",
            },
            active=True,
        )


    def test_game_list_success_two_games(self):
        data = {
            "game_name_list": ['waterloo', 'diplomacy'],
        }

        request = self.factory.post(reverse('game_list'), data=json.dumps(data), content_type='json')
        response = game_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(len(response_content["game_list"]), 2)

    def test_game_list_success_two_games_and_unknown_games(self):
        data = {
            "game_name_list": ['waterloo', 'diplomacy', 'terra mystica'],
        }
        request = self.factory.post(reverse('game_list'), data=json.dumps(data), content_type='json')
        response = game_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(len(response_content["game_list"]), 2)

    def test_game_list_without_names_returns_active_games(self):
        self.diplomacy.active = False
        self.diplomacy.save()
        data = {
        }

        request = self.factory.post(reverse('game_list'), data=json.dumps(data), content_type='json')
        response = game_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(
            [game["name"] for game in response_content["game_list"]],
            ['waterloo'],
        )

    def test_game_list_rejects_a_non_list(self):
        data = {
            "game_name_list": "waterloo",
        }

        request = self.factory.post(reverse('game_list'), data=json.dumps(data), content_type='json')
        response = game_list(request)
        self.assertEqual(response.status_code, 400)

    def test_game_list_empty_unknown_game(self):
        data = {
            "game_name_list": ['terra_mystica', 'diplomacy'],
        }

        request = self.factory.post(reverse('session_get'), data=json.dumps(data), content_type='json')
        response = game_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(len(response_content["game_list"]), 1)
        self.assertEqual(len(response_content["game_list"][0]["variant"]), 2)

    def test_game_list_failure_invalid_json(self):
        request = self.factory.post(reverse('game_list'), data="not a valid json", content_type='json')
        response = game_list(request)
        self.assertEqual(response.status_code, 400)

    def test_game_list_returns_inactive_game(self):
        self.diplomacy.active = False
        self.diplomacy.save()
        data = {
            "game_name_list": ['waterloo', 'diplomacy'],
        }

        request = self.factory.post(reverse('game_list'), data=json.dumps(data), content_type='json')
        response = game_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(
            sorted(game["name"] for game in response_content["game_list"]),
            ['diplomacy', 'waterloo'],
        )

    def test_game_list_rejects_get_request(self):
        request = self.factory.get(reverse('game_list'))
        response = game_list(request)
        self.assertEqual(response.status_code, 405)

