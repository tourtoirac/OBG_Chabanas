import json
from django.test import TestCase, RequestFactory
from django.http import JsonResponse, HttpResponse
from Game.models import Game, Session
from Game.tools import (
    generate_session_code,
    return_session_json,
    is_session_participant,
)
from Game.views import (
    session_create,
    session_get,
    session_list,
    session_join,
    session_get_archive,
    session_archive,
    session_update,
)
from Chabanas.params_ext import UNAUTHORIZED

class GameModelTest(TestCase):
    def test_create_game(self):
        game = Game.objects.create(name="Test Game", max_players=4, max_watchers=20)
        self.assertEqual(game.name, "Test Game")
        self.assertEqual(game.max_players, 4)
        self.assertTrue(game.active)

    def test_create_session(self):
        game = Game.objects.create(name="Test Game")
        session = Session.objects.create(
            game=game,
            player1_nickname="Player1",
            player1_key="key1",
            player2_nickname="Player2",
            player2_key="key2",
            active=True
        )
        self.assertEqual(session.game.name, "Test Game")
        self.assertEqual(session.player1_nickname, "Player1")
        self.assertTrue(session.active)

class ToolTest(TestCase):
    def test_generate_session_code(self):
        code1 = generate_session_code()
        code2 = generate_session_code()
        self.assertEqual(len(code1), 8)
        self.assertNotEqual(code1, code2)

    def test_return_session_json(self):
        game = Game.objects.create(name="Test Game", game_json={"score": 0})
        session = Session.objects.create(
            game=game,
            player1_nickname="P1",
            player1_key="K1",
            player2_nickname="P2",
            player2_key="K2",
            active=True
        )
        
        # Test avec sat_list par défaut
        data = return_session_json(session)
        self.assertEqual(data["name"], "Test Game")
        self.assertEqual(data["game_json"], {"score": 0})

        # Test avec sat_list spécifique sans game_json
        data_no_json = return_session_json(session, sat_list=["code"])
        self.assertNotIn("game_json", data_no_json)

    def test_is_session_participant(self):
        game = Game.objects.create(name="Test Game")
        session = Session.objects.create(
            game=game,
            player1_nickname="P1",
            player1_key="K1",
            player2_nickname="P2",
            player2_key="K2",
            active=True
        )
        
        # Cas : Participant 1
        self.assertTrue(is_session_participant(session, "P1", "K1"))
        # Cas : Participant 2
        self.assertTrue(is_session_participant(session, "P2", "K2"))
        # Cas : Non participant
        self.assertFalse(is_session_participant(session, "Stranger", "K3"))

class ViewTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(
            name="Test Game", 
            game_json={"score": 0},
            max_players=2
        )

    def test_session_create_success(self):
        data = {
            "name": "Test Game",
            "player_nickname": "Player1",
            "player_key": "key1"
        }
        request = self.factory.post("/", data=json.dumps(data), content_type='application/json')
        response = session_create(request)
        
        self.assertEqual(response.status_code, 201)
        self.assertIn("session_key", response.json())
        self.assertIn("session_code", response.json())

    def test_session_create_not_found(self):
        data = {
            "name": "NonExistent",
            "player_nickname": "P1",
            "player_key": "K1"
        }
        request = self.factory.post("/", data=json.dumps(data), content_type='application/json')
        response = session_create(request)
        self.assertEqual(response.status_code, 404)

    def test_session_get_success(self):
        session = Session.objects.create(
            game=self.game,
            code="CODE123",
            player1_nickname="P1",
            player1_key="K1",
            player2_nickname="P2",
            player2_key="K2",
            active=True
        )
        data = {"session_code": "CODE123"}
        request = self.factory.post("/", data=json.dumps(data), content_type='application/json')
        response = session_get(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["session"]["code"], "CODE123")

    def test_session_list(self):
        Session.objects.create(game=self.game, code="C1", player1_nickname="P1", player1_key="K1", active=True)
        
        request = self.factory.post("/", data=json.dumps({}), content_type='application/json')
        response = session_list(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("sessions", response.json())
        self.assertIn("Test Game", response.json()["sessions"])

    def test_session_join_success(self):
        session = Session.objects.create(
            game=self.game,
            code="JOIN_CODE",
            player1_nickname="P1",
            player1_key="K1",
            player2_nickname="",
            player2_key="",
            active=True
        )
        data = {
            "code": "JOIN_CODE",
            "nickname": "P2",
            "key": "K2"
        }
        request = self.factory.post("/", data=json.dumps(data), content_type='application/json')
        response = session_join(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(session.player2_nickname, "P2")
        self.assertEqual(session.player2_key, "K2")

    def test_session_join_full(self):
        session = Session.objects.create(
            game=self.game,
            code="FULL_CODE",
            player1_nickname="P1",
            player1_key="K1",
            player2_nickname="P2",
            player2_key="K2",
            active=True
        )
        data = {
            "code": "FULL_CODE",
            "nickname": "P3",
            "key": "K3"
        }
        request = self.factory.post("/", data=json.dumps(data), content_type='application/json')
        response = session_join(request)
        self.assertEqual(response.status_code, 409)

    def test_session_archive(self):
        session = Session.objects.create(
            game=self.game,
            code="ARCHIVE_ME",
            player1_nickname="P1",
            player1_key="K1",
            active=True
        )
        data = {"key": str(session.key)}
        request = self.factory.post("/", data=json.dumps(data), content_type='application/json')
        response = session_archive(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(session.active)

    def test_session_get_archive(self):
        session = Session.objects.create(
            game=self.game,
            code="OLD_CODE",
            player1_nickname="P1",
            player1_key="K1",
            active=False
        )
        data = {"key": str(session.key)}
        request = self.factory.post("/", data=json.dumps(data), content_type='application/json')
        response = session_get_archive(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["session"]["active"])

    def test_session_update_success(self):
        session = Session.objects.create(
            game=self.game,
            code="UPDATE_ME",
            player1_nickname="P1",
            player1_key="K1",
            active=True
        )
        data = {
            "key": str(session.key),
            "game_json": {"score": 100}
        }
        request = self.factory.post("/", data=json.dumps(data), content_type='application/json')
        response = session_update(request)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(session.game_json, {"score": 100})

    def test_session_update_unauthorized(self):
        session = Session.objects.create(
            game=self.game,
            code="UPDATE_ME",
            player1_nickname="P1",
            player1_key="K1",
            active=False
        )
        data = {
            "key": str(session.key),
            "game_json": {"score": 100}
        }
        request = self.factory.post("/", data=json.dumps(data), content_type='application/json')
        response = session_update(request)
        self.assertEqual(response.status_code, 401)
