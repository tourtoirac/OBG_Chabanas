import json

from django.shortcuts import Http404
from django.test import TestCase, RequestFactory
from django.urls import reverse

from Game.models import Game, Variant
from Game.views import game_list


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

    def test_game_list_failure_missing_data(self):
        data = {
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

