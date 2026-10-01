import json
import uuid

from datetime import datetime, timedelta, UTC
from unittest.mock import patch

from django.shortcuts import Http404
from django.test import TestCase, RequestFactory
from django.urls import reverse

from Game.models import Game, Variant
from Session.tools import (
    generate_session_code,
    is_session_participant,
    return_player_json,
    return_session_json,
)
from Session.models import Session, Player
from Session.views import (session_create, session_get, session_list, session_archive, session_get_archive,
                           session_join, session_update)


class SessionModelTest(TestCase):
    def test_create_session(self):
        game = Game.objects.create(name="Test Game")
        session = Session.objects.create(
            game=game,
            active=True,
            access_key='test_key'
        )
        self.assertEqual(session.game.name, "Test Game")
        self.assertTrue(session.active)

    def test_session_str(self):
        game = Game.objects.create(name="Test Game")
        session = Session.objects.create(
            game=game,
            code='1234',
            active=True
        )
        self.assertEqual(session.__str__(), "Test Game - 1234")


class PlayerModelTest(TestCase):
    def test_create_player(self):
        game = Game.objects.create(name="Test Game")
        session = Session.objects.create(
            game=game,
            active=True,
            access_key='test_key'
        )
        player = Player.objects.create(
            session=session,
            nickname="Player1",
            owner=True,
        )
        self.assertEqual(player.nickname, "Player1")
        self.assertTrue(player.owner)

    def test_player_str(self):
        game = Game.objects.create(name="Test Game")
        session = Session.objects.create(game=game, active=True)
        player = Player.objects.create(
            session=session,
            nickname="Player1",
            owner=True,
        )
        self.assertEqual(player.__str__(), "Test Game - Player1")

class ToolTest(TestCase):
    def test_generate_session_code(self):
        code1 = generate_session_code()
        code2 = generate_session_code()
        self.assertEqual(len(code1), 8)
        self.assertNotEqual(code1, code2)

    def test_is_session_participant(self):
        game = Game.objects.create(name="Test Game")
        session = Session.objects.create(
            game=game,
            active=True
        )
        Player.objects.create(
            session=session,
            nickname="P1",
            key="",
            owner=True,
        )
        Player.objects.create(
            session=session,
            nickname="P2",
            key="",
            owner=False,
        )

        # Cas : Participant 1
        self.assertTrue(is_session_participant(session, "P1", ""))
        # Cas : Participant 2
        self.assertTrue(is_session_participant(session, "P2", ""))
        # Cas : Non participant
        self.assertFalse(is_session_participant(session, "Stranger", ""))

    def test_is_session_participant_wrong_key(self):
        game = Game.objects.create(name="Test Game")
        session = Session.objects.create(
            game=game,
            active=True
        )
        Player.objects.create(
            session=session,
            nickname="P1",
            key="K1",
            owner=True,
        )

        self.assertFalse(is_session_participant(session, "P1", "K2"))

    @patch('Session.tools.secrets.choice', side_effect=['A'] * 8 + ['B'] * 8)
    def test_generate_session_code_retries_on_existing_active_code(self, mock_choice):
        game = Game.objects.create(name="Test Game")
        Session.objects.create(
            game=game,
            code='AAAAAAAA',
            active=True
        )

        code = generate_session_code()
        self.assertEqual(code, 'BBBBBBBB')
        self.assertEqual(mock_choice.call_count, 16)

    @patch('Session.tools.secrets.choice', return_value='A')
    def test_generate_session_code_reuses_archived_code(self, mock_choice):
        game = Game.objects.create(name="Test Game")
        Session.objects.create(
            game=game,
            code='AAAAAAAA',
            active=False
        )

        self.assertEqual(generate_session_code(), 'AAAAAAAA')

    def test_return_session_json_without_sat_list(self):
        game = Game.objects.create(name="Test Game")
        session = Session.objects.create(
            game=game,
            code='1234',
            variant_name='default',
            access_key='AK1',
            allows_watchers=False,
            game_json={"game": "json"},
        )
        Player.objects.create(
            session=session,
            nickname="P1",
            key="K1",
            owner=True,
        )

        data = return_session_json(session)
        self.assertEqual(data["name"], "Test Game")
        self.assertEqual(data["key"], session.key)
        self.assertEqual(data["code"], '1234')
        self.assertEqual(data["variant"], 'default')
        self.assertEqual(data["access_key"], 'AK1')
        self.assertFalse(data["allows_watchers"])
        self.assertTrue(data["active"])
        self.assertEqual(len(data["players"]), 1)
        self.assertNotIn('game_json', data)
        self.assertNotIn('key', data["players"][0])

    def test_return_session_json_with_sat_list(self):
        game = Game.objects.create(name="Test Game")
        session = Session.objects.create(
            game=game,
            code='1234',
            max_players=3,
            max_watchers=7,
            game_json={"game": "json"},
        )
        Player.objects.create(
            session=session,
            nickname="P1",
            key="K1",
            owner=True,
        )

        data = return_session_json(session, sat_list=['game_json', 'player_key'])
        self.assertEqual(data["game_json"], {
            "game": {"max_players": 3, "max_watchers": 7},
        })
        self.assertEqual(data["players"][0]["key"], "K1")
        session.refresh_from_db()
        self.assertEqual(session.game_json, {"game": "json"})

    def test_return_player_json_without_sat_list(self):
        game = Game.objects.create(name="Test Game")
        session = Session.objects.create(game=game)
        player = Player.objects.create(
            session=session,
            nickname="P1",
            key="K1",
            owner=True,
        )

        data = return_player_json(player)
        self.assertEqual(data, {"nickname": "P1", "owner": True})

    def test_return_player_json_with_sat_list(self):
        game = Game.objects.create(name="Test Game")
        session = Session.objects.create(game=game)
        player = Player.objects.create(
            session=session,
            nickname="P1",
            key="K1",
            owner=True,
        )

        data = return_player_json(player, sat_list=['key'])
        self.assertEqual(data, {"nickname": "P1", "owner": True, "key": "K1"})

class SessionCreateTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(
            name="waterloo",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "waterloo",
            },
            active=True,
        )

        self.variant = Variant.objects.create(
            game=self.game,
            name="solo",
            game_json={
                "variant": "waterloo solo",
            },
        )

    def test_session_create_success(self):
        data = {
            "game_name": "waterloo",
            "nickname": "Chins",
            "key": "123456789",
        }

        request = self.factory.post(reverse('session_create'), data=json.dumps(data), content_type='json')
        response = session_create(request)
        self.assertEqual(response.status_code, 201)
        json_response = json.loads(response.content)
        session = Session.objects.get(key=json_response["session_key"])
        self.assertEqual(session.game_json, {'game': 'waterloo'})

    def test_session_create_failure_missing_data(self):
        data = {
            "game_name": "waterloo",
            "key": "123456789",
        }

        request = self.factory.post(reverse('session_create'), data=json.dumps(data), content_type='json')
        response = session_create(request)
        self.assertEqual(response.status_code, 400)

    def test_session_create_success_with_variant(self):
        data = {
            "game_name": "waterloo",
            "nickname": "Chins",
            "key": "123456789",
            "variant_name": "solo",
        }

        request = self.factory.post(reverse('session_create'), data=json.dumps(data), content_type='json')
        response = session_create(request)
        self.assertEqual(response.status_code, 201)
        json_response = json.loads(response.content)
        session = Session.objects.get(key=json_response["session_key"])
        self.assertEqual(session.game_json, {'variant': 'waterloo solo'})

    def test_session_create_failure_unknown_game(self):
        data = {
            "game_name": "some game",
            "nickname": "Chins",
            "key": "123456789",
        }

        request = self.factory.post(reverse('session_create'), data=json.dumps(data), content_type='json')
        with self.assertRaises(Http404):
            session_create(request)

    def test_session_create_failure_unknown_variant(self):
        data = {
            "game_name": "some game",
            "nickname": "Chins",
            "key": "123456789",
            "variant": "unknown"
        }

        request = self.factory.post(reverse('session_create'), data=json.dumps(data), content_type='json')
        with self.assertRaises(Http404):
            session_create(request)

    def test_session_create_failure_quota_exceeded(self):
        for i in range(5):
            session = Session.objects.create(
                code=f"code_{i}",
                game=self.game,
                active=True
            )
            Player.objects.create(
                session=session,
                nickname=f"player_{i}",
                key=f"key_{i}",
                owner=True,
            )

        data = {
            "game_name": "waterloo",
            "nickname": "Chins",
            "key": "123456789",
        }

        request = self.factory.post(reverse('session_create'), data=json.dumps(data), content_type='json')
        response = session_create(request)
        self.assertEqual(response.status_code, 409)

    def test_session_create_success_creates_owner_player(self):
        data = {
            "game_name": "waterloo",
            "nickname": "Chins",
            "key": "123456789",
        }

        request = self.factory.post(reverse('session_create'), data=json.dumps(data), content_type='json')
        response = session_create(request)
        self.assertEqual(response.status_code, 201)
        json_response = json.loads(response.content)
        session = Session.objects.get(key=json_response["session_key"])
        player = Player.objects.get(session=session)
        self.assertEqual(player.nickname, "Chins")
        self.assertEqual(player.key, "123456789")
        self.assertTrue(player.owner)
        self.assertEqual(session.variant_name, 'default')
        self.assertEqual(session.code, json_response["session_code"])
        self.assertEqual(len(session.code), 8)
        self.assertTrue(session.active)
        self.assertFalse(session.locked)

    def test_session_create_success_with_session_limits(self):
        data = {
            "game_name": "waterloo",
            "nickname": "Chins",
            "key": "123456789",
            "session_max_players": 3,
            "session_max_watchers": 4,
        }

        request = self.factory.post(reverse('session_create'), data=json.dumps(data), content_type='json')
        response = session_create(request)
        self.assertEqual(response.status_code, 201)
        json_response = json.loads(response.content)
        session = Session.objects.get(key=json_response["session_key"])
        self.assertEqual(session.max_players, 3)
        self.assertEqual(session.max_watchers, 4)

    def test_session_create_success_with_access_key_and_no_watchers(self):
        data = {
            "game_name": "waterloo",
            "nickname": "Chins",
            "key": "123456789",
            "access_key": "AK1",
            "allows_watchers": False,
        }

        request = self.factory.post(reverse('session_create'), data=json.dumps(data), content_type='json')
        response = session_create(request)
        self.assertEqual(response.status_code, 201)
        json_response = json.loads(response.content)
        session = Session.objects.get(key=json_response["session_key"])
        self.assertEqual(session.access_key, "AK1")
        self.assertFalse(session.allows_watchers)

    def test_session_create_success_with_variant_uses_variant_limits(self):
        variant = Variant.objects.create(
            game=self.game,
            name="duo",
            max_players=7,
            max_watchers=15,
            game_json={
                "variant": "waterloo duo",
            },
        )
        data = {
            "game_name": "waterloo",
            "nickname": "Chins",
            "key": "123456789",
            "variant_name": "duo",
        }

        request = self.factory.post(reverse('session_create'), data=json.dumps(data), content_type='json')
        response = session_create(request)
        self.assertEqual(response.status_code, 201)
        json_response = json.loads(response.content)
        session = Session.objects.get(key=json_response["session_key"])
        self.assertEqual(session.variant_name, variant.name)
        self.assertEqual(session.max_players, 7)
        self.assertEqual(session.max_watchers, 15)
        self.assertEqual(session.game_json, {'variant': 'waterloo duo'})

    def test_session_create_success_session_limits_override_variant_limits(self):
        Variant.objects.create(
            game=self.game,
            name="duo",
            max_players=7,
            max_watchers=15,
        )
        data = {
            "game_name": "waterloo",
            "nickname": "Chins",
            "key": "123456789",
            "variant_name": "duo",
            "session_max_players": 5,
            "session_max_watchers": 6,
        }

        request = self.factory.post(reverse('session_create'), data=json.dumps(data), content_type='json')
        response = session_create(request)
        self.assertEqual(response.status_code, 201)
        json_response = json.loads(response.content)
        session = Session.objects.get(key=json_response["session_key"])
        self.assertEqual(session.max_players, 5)
        self.assertEqual(session.max_watchers, 6)

class SessionGetTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(
            name="waterloo",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "waterloo",
            },
            active=True,
        )
        self.session = Session.objects.create(
            game=self.game,
            game_json={
                "waterloo": "json",
            }
        )
        Player.objects.create(
            session=self.session,
            nickname="P1",
            key="K1",
            owner=True,
        )

    def test_session_get_success(self):
        data = {
            "session_code": self.session.code,
            "sat_list": ["game_json"]
        }

        request = self.factory.post(reverse('session_get'), data=json.dumps(data), content_type='json')
        response = session_get(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(response_content["session"]['game_json'], {'game': {'max_players': 2, 'max_watchers': 10}, 'waterloo': 'json'})

    def test_session_get_success_with_players_key(self):
        data = {
            "session_code": self.session.code,
            "sat_list": ["game_json", "player_key"]
        }

        request = self.factory.post(reverse('session_get'), data=json.dumps(data), content_type='json')
        response = session_get(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(response_content["session"]['players'][0]['key'], 'K1')

    def test_session_get_success_without_players_key(self):
        data = {
            "session_code": self.session.code,
            "sat_list": ["game_json"]
        }

        request = self.factory.post(reverse('session_get'), data=json.dumps(data), content_type='json')
        response = session_get(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertFalse('key' in response_content["session"]['players'][0])

    def test_session_get_failure_missing_data(self):
        data = {
        }

        request = self.factory.post(reverse('session_get'), data=json.dumps(data), content_type='json')
        response = session_get(request)
        self.assertEqual(response.status_code, 400)

    def test_create_session_failure_unknown_session(self):
        data = {
            "session_code": "some code",
        }

        request = self.factory.post(reverse('session_get'), data=json.dumps(data), content_type='json')
        with self.assertRaises(Http404):
            session_get(request)

    def test_session_get_failure_inactive_session(self):
        self.session.active = False
        self.session.save()
        data = {
            "session_code": self.session.code,
        }

        request = self.factory.post(reverse('session_get'), data=json.dumps(data), content_type='json')
        with self.assertRaises(Http404):
            session_get(request)

    def test_session_get_success_without_sat_list(self):
        data = {
            "session_code": self.session.code,
        }

        request = self.factory.post(reverse('session_get'), data=json.dumps(data), content_type='json')
        response = session_get(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        session_data = response_content["session"]
        self.assertNotIn('game_json', session_data)
        self.assertEqual(session_data["name"], "waterloo")
        self.assertEqual(session_data["key"], str(self.session.key))
        self.assertEqual(session_data["players"], [{"nickname": "P1", "owner": True}])

class SessionListTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(
            name="waterloo",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "waterloo",
            },
            active=True,
        )
        self.session = Session.objects.create(
            game=self.game,
            game_json={
                "waterloo": "json",
            }
        )
        Player.objects.create(
            session=self.session,
            nickname="P1",
            key="K1",
            owner=True,
        )

    def test_session_list_success(self):
        data = {
            "game_name_list": ['waterloo'],
        }

        request = self.factory.post(reverse('session_get'), data=json.dumps(data), content_type='json')
        response = session_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(len(response_content["sessions"]), 1)

    def test_session_list_failure_missing_data(self):
        data = {
        }

        request = self.factory.post(reverse('session_list'), data=json.dumps(data), content_type='json')
        response = session_list(request)
        self.assertEqual(response.status_code, 400)

    def test_session_list_empty(self):
        data = {
            "game_name_list": ['diplomacy'],
        }

        request = self.factory.post(reverse('session_get'), data=json.dumps(data), content_type='json')
        response = session_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(len(response_content["sessions"]), 0)

    def test_session_list_deactivates_expired_sessions(self):
        Session.objects.filter(pk=self.session.pk).update(
            created_at=datetime.now(UTC) - timedelta(days=8),
        )
        data = {
            "game_name_list": ['waterloo'],
        }

        request = self.factory.post(reverse('session_list'), data=json.dumps(data), content_type='json')
        response = session_list(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertFalse(self.session.active)
        self.assertEqual(self.session.code, '')

    def test_session_list_keeps_recent_sessions_active(self):
        self.session.code = '1234'
        self.session.save()
        Session.objects.filter(pk=self.session.pk).update(
            created_at=datetime.now(UTC) - timedelta(days=6),
        )
        data = {
            "game_name_list": ['waterloo'],
        }

        request = self.factory.post(reverse('session_list'), data=json.dumps(data), content_type='json')
        response = session_list(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertTrue(self.session.active)
        self.assertNotEqual(self.session.code, '')

    def test_session_list_excludes_inactive_session(self):
        self.session.active = False
        self.session.save()
        data = {
            "game_name_list": ['waterloo'],
        }

        request = self.factory.post(reverse('session_list'), data=json.dumps(data), content_type='json')
        response = session_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(len(response_content["sessions"]["waterloo"]), 0)

    def test_session_list_excludes_inactive_game(self):
        self.game.active = False
        self.game.save()
        data = {
            "game_name_list": ['waterloo'],
        }

        request = self.factory.post(reverse('session_list'), data=json.dumps(data), content_type='json')
        response = session_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(len(response_content["sessions"]), 0)
        self.assertNotIn('waterloo', response_content["sessions"])

class SessionJoinTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(
            name="waterloo",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "waterloo",
            },
            active=True,
        )
        self.session = Session.objects.create(
            game=self.game,
            code='code1',
            max_players=2,
            access_key="SK1",
            game_json={
                "waterloo": "json",
            }
        )
        self.session2 = Session.objects.create(
            game=self.game,
            code='code2',
            max_players=2,
            access_key="",
            game_json={
                "waterloo": "json",
            }
        )
        Player.objects.create(
            session=self.session,
            nickname="P1",
            key="PK1",
            owner=True,
        )
        Player.objects.create(
            session=self.session2,
            nickname="P2",
            key="PK2",
            owner=True,
        )

    def test_session_join_success_owner_with_access_key(self):
        data = {
            "session_code": 'code1',
            "nickname": "P1",
            "key": "PK1",
            "access_key": "SK1"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 200)

    def test_session_join_failure_incorrect_access_key(self):
        data = {
            "session_code": 'code1',
            "nickname": "P1",
            "key": "PK1",
            "access_key": "SK3"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 401)

    def test_session_join_failure_incorrect_player_key(self):
        data = {
            "session_code": 'code1',
            "nickname": "P1",
            "key": "PKX",
            "access_key": "SK1"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 401)

    def test_session_join_success_owner_with_empty_access_key(self):
        data = {
            "session_code": 'code2',
            "nickname": "P2",
            "key": "PK2",
            "access_key": ""
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 200)

    def test_session_join_failure_missing_data(self):
        data = {
        }

        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 400)

    def test_session_join_new_user(self):
        data = {
            "session_code": 'code1',
            "nickname": "P2",
            "key": "K2",
            "access_key": "SK1"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 200)

    def test_session_join_failure_game_full(self):
        Player.objects.create(
            session=self.session,
            nickname="P2",
            owner=False,
        )
        data = {
            "session_code": 'code1',
            "nickname": "P3",
            "key": "K3",
            "access_key": "SK1"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 409)

    def test_session_join_failure_unknown_session_code(self):
        data = {
            "session_code": 'unknown code',
            "nickname": "P2",
            "key": "K2",
            "access_key": ""
        }

        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        with self.assertRaises(Http404):
            session_join(request)

    def test_session_join_success_player_without_key(self):
        """
        The user key is optional: a player joins without one and simply gets a
        new seat, stored with an empty key.
        """
        data = {
            "session_code": 'code1',
            "nickname": "P2",
            "access_key": "SK1",
        }

        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Player.objects.filter(session=self.session).count(), 2)
        self.assertEqual(Player.objects.get(session=self.session, nickname="P2").key, '')

    def test_session_join_success_player_without_key_comes_back(self):
        """
        Once seated without a key, the same player gets back that seat instead
        of being refused as an impostor, because the empty key matches.
        """
        data = {
            "session_code": 'code1',
            "nickname": "P2",
            "access_key": "SK1",
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        self.assertEqual(session_join(request).status_code, 200)

        again = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        self.assertEqual(session_join(again).status_code, 200)
        self.assertEqual(Player.objects.filter(session=self.session).count(), 2, (
            "revenir sans clé ne doit pas créer un second siege"
        ))

    def test_session_join_failure_wrong_key_for_a_known_nickname(self):
        """
        A key that does not match the one already stored for that nickname is
        still refused: an empty key is a valid key, not a wildcard.
        """
        Player.objects.create(
            session=self.session,
            nickname="P2",
            key="",
            owner=False,
        )
        data = {
            "session_code": 'code1',
            "nickname": "P2",
            "key": "K9",
            "access_key": "SK1",
        }

        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Player.objects.get(session=self.session, nickname="P2").key, '')

    def test_session_join_failure_unknown_role(self):
        data = {
            "session_code": 'code1',
            "nickname": "P2",
            "key": "K2",
            "role": "admin",
            "access_key": "SK1",
        }

        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Player.objects.filter(session=self.session).count(), 1)

    def test_session_join_watcher_without_key(self):
        """
        A spectator only gives a nickname: no key, and no row in session_players.
        """
        data = {
            "session_code": 'code1',
            "nickname": "S1",
            "role": "watcher",
            "access_key": "SK1",
        }

        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)

        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content['game_json'],
            {'game': {'max_players': 2, 'max_watchers': 10}, 'waterloo': 'json'},
        )
        self.assertEqual(Player.objects.filter(session=self.session).count(), 1, (
            "un spectateur ne doit pas etre enregistre en base"
        ))
        self.assertFalse(
            Player.objects.filter(session=self.session, nickname="S1").exists()
        )

    def test_session_join_watcher_does_not_consume_a_player_seat(self):
        Player.objects.create(
            session=self.session,
            nickname="P2",
            key="K2",
            owner=False,
        )
        self.assertEqual(
            len(Player.objects.filter(session=self.session)), self.session.max_players
        )

        data = {
            "session_code": 'code1',
            "nickname": "S1",
            "role": "watcher",
            "access_key": "SK1",
        }

        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)

        self.assertEqual(response.status_code, 200, (
            "un spectateur doit pouvoir arriver sur une partie complete"
        ))
        self.assertEqual(Player.objects.filter(session=self.session).count(), 2)

    def test_session_join_watcher_failure_incorrect_access_key(self):
        data = {
            "session_code": 'code1',
            "nickname": "S1",
            "role": "watcher",
            "access_key": "SK3",
        }

        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(Player.objects.filter(session=self.session).count(), 1)

    def test_session_join_watcher_failure_watchers_not_allowed(self):
        self.session.allows_watchers = False
        self.session.save()
        data = {
            "session_code": 'code1',
            "nickname": "S1",
            "role": "watcher",
            "access_key": "SK1",
        }

        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Player.objects.filter(session=self.session).count(), 1)

    def test_session_join_watcher_failure_locked_session(self):
        self.session.locked = True
        self.session.save()
        data = {
            "session_code": 'code1',
            "nickname": "S1",
            "role": "watcher",
            "access_key": "SK1",
        }

        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Player.objects.filter(session=self.session).count(), 1)

    def test_session_join_watcher_nickname_does_not_block_a_later_player(self):
        """
        A spectator nickname is never stored, so it cannot collide with the
        nickname a player will choose.
        """
        data = {
            "session_code": 'code1',
            "nickname": "P2",
            "key": "K2",
            "access_key": "SK1",
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        self.assertEqual(session_join(request).status_code, 200)
        self.assertEqual(Player.objects.get(session=self.session, nickname="P2").key, "K2")

    def test_session_join_new_user_is_added_as_non_owner(self):
        data = {
            "session_code": 'code1',
            "nickname": "P2",
            "key": "K2",
            "access_key": "SK1"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Player.objects.filter(session=self.session).count(), 2)
        new_player = Player.objects.get(session=self.session, nickname="P2")
        self.assertEqual(new_player.key, "K2")
        self.assertFalse(new_player.owner)

    def test_session_join_returns_session_game_json(self):
        data = {
            "session_code": 'code1',
            "nickname": "P2",
            "key": "K2",
            "access_key": "SK1"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(
            response_content['game_json'],
            {'game': {'max_players': 2, 'max_watchers': 10}, 'waterloo': 'json'},
        )
        self.assertEqual(response_content["access_key"], "SK1")
        self.assertEqual(len(response_content["players"]), 2)
        self.assertNotIn('key', response_content["players"][1])

    def test_session_join_reconnect_does_not_duplicate_player(self):
        data = {
            "session_code": 'code1',
            "nickname": "P1",
            "key": "PK1",
            "access_key": "SK1"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Player.objects.filter(session=self.session).count(), 1)

    def test_session_join_failure_inactive_session(self):
        self.session.active = False
        self.session.save()
        data = {
            "session_code": 'code1',
            "nickname": "P2",
            "key": "K2",
            "access_key": "SK1"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        with self.assertRaises(Http404):
            session_join(request)
        self.assertEqual(Player.objects.filter(session=self.session).count(), 1)

    def test_session_join_failure_locked_session(self):
        self.session.locked = True
        self.session.save()
        data = {
            "session_code": 'code1',
            "nickname": "P2",
            "key": "K2",
            "access_key": "SK1"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Player.objects.filter(session=self.session).count(), 1)

    def test_session_join_success_returning_player_on_locked_session(self):
        self.session.locked = True
        self.session.save()
        data = {
            "session_code": 'code1',
            "nickname": "P1",
            "key": "PK1",
            "access_key": "SK1"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Player.objects.filter(session=self.session).count(), 1)

    def test_session_join_success_returning_player_when_game_is_full(self):
        Player.objects.create(
            session=self.session,
            nickname="P2",
            key="K2",
            owner=False,
        )
        data = {
            "session_code": 'code1',
            "nickname": "P1",
            "key": "PK1",
            "access_key": "SK1"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Player.objects.filter(session=self.session).count(), 2)

    def test_session_join_success_returning_player_when_locked_and_full(self):
        self.session.locked = True
        self.session.save()
        Player.objects.create(
            session=self.session,
            nickname="P2",
            key="K2",
            owner=False,
        )
        data = {
            "session_code": 'code1',
            "nickname": "P1",
            "key": "PK1",
            "access_key": "SK1"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Player.objects.filter(session=self.session).count(), 2)


class SessionGetArchiveTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(
            name="waterloo",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "waterloo",
            },
            active=True,
        )
        self.session = Session.objects.create(
            game=self.game,
            code='1234',
            game_json={
                "waterloo": "json",
            },
            active=False
        )
        Player.objects.create(
            session=self.session,
            nickname="P1",
            key="K1",
            owner=True,
        )

    def test_session_get_archive_success(self):
        data = {
            "key": str(self.session.key),
        }

        request = self.factory.post(reverse('session_get_archive'), data=json.dumps(data), content_type='json')
        response = session_get_archive(request)
        self.assertEqual(response.status_code, 200)

    def test_session_get_archive_failure_missing_data(self):
        data = {
        }

        request = self.factory.post(reverse('session_get_archive'), data=json.dumps(data), content_type='json')
        response = session_get_archive(request)
        self.assertEqual(response.status_code, 400)

    def test_session_list_failure_unknown_session_key(self):
        data = {
            "key": str(uuid.uuid4()),
        }

        request = self.factory.post(reverse('session_get_archive'), data=json.dumps(data), content_type='json')
        with self.assertRaises(Http404):
            session_get_archive(request)

    def test_session_list_failure_active_session_key(self):
        active_session = Session.objects.create(
            game=self.game,
            game_json={
                "waterloo": "json",
            },
            active=True,
            code='456',
        )
        data = {
            "key": str(active_session.key),
        }

        request = self.factory.post(reverse('session_get_archive'), data=json.dumps(data), content_type='json')
        with self.assertRaises(Http404):
            session_get_archive(request)

class SessionArchiveTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(
            name="waterloo",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "waterloo",
            },
            active=True,
        )
        self.session = Session.objects.create(
            game=self.game,
            code='1234',
            game_json={
                "waterloo": "json",
            },
            active=True
        )
        Player.objects.create(
            session=self.session,
            nickname="P1",
            key="K1",
            owner=True,
        )

    def test_session_archive_success(self):
        data = {
            "key": str(self.session.key),
        }

        request = self.factory.post(reverse('session_archive'), data=json.dumps(data), content_type='json')
        response = session_archive(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertFalse(self.session.active)

    def test_session_archive_failure_missing_data(self):
        data = {
        }

        request = self.factory.post(reverse('session_archive'), data=json.dumps(data), content_type='json')
        response = session_archive(request)
        self.assertEqual(response.status_code, 400)

    def test_session_archive_failure_unknown_session_key(self):
        data = {
            "key": str(uuid.uuid4()),
        }

        request = self.factory.post(reverse('session_archive'), data=json.dumps(data), content_type='json')
        with self.assertRaises(Http404):
            session_archive(request)

    def test_session_archive_failure_inactive_session_key(self):
        active_session = Session.objects.create(
            game=self.game,
            game_json={
                "waterloo": "json",
            },
            active=False,
            code='456',
        )
        data = {
            "key": str(active_session.key),
        }

        request = self.factory.post(reverse('session_archive'), data=json.dumps(data), content_type='json')
        with self.assertRaises(Http404):
            session_archive(request)

class SessionUpdateTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(
            name="waterloo",
            max_players=2,
            max_watchers=10,
            max_sessions=5,
            game_json={
                "game": "waterloo",
            },
            active=True,
        )
        self.session = Session.objects.create(
            game=self.game,
            code='1234',
            game_json={
                "waterloo": "json",
            },
            active=True,
            locked=False,
        )
        Player.objects.create(
            session=self.session,
            nickname="P1",
            key="K1",
            owner=True,
        )

    def test_session_update_game_json_success(self):
        data = {
            "key": str(self.session.key),
            "game_json": {"waterloo": "new json"}
        }

        request = self.factory.post(reverse('session_update'), data=json.dumps(data), content_type='json')
        response = session_update(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.game_json, {"waterloo": "new json"})

    def test_session_update_locked_success(self):
        data = {
            "key": str(self.session.key),
            "locked": True
        }

        request = self.factory.post(reverse('session_update'), data=json.dumps(data), content_type='json')
        response = session_update(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertTrue(self.session.locked)

    def test_session_update_failure_missing_data(self):

        data = {
        }

        request = self.factory.post(reverse('session_update'), data=json.dumps(data), content_type='json')
        response = session_update(request)
        self.assertEqual(response.status_code, 400)

    def test_session_update_failure_unknown_session_key(self):
        data = {
            "key": str(uuid.uuid4()),
            "game_json": {"waterloo": "new json"}
        }

        request = self.factory.post(reverse('session_update'), data=json.dumps(data), content_type='json')
        with self.assertRaises(Http404):
            session_update(request)

    def test_session_update_failure_inactive_session(self):
        active_session = Session.objects.create(
            game=self.game,
            game_json={
                "waterloo": "json",
            },
            active=False,
            code='456',
        )
        data = {
            "key": str(active_session.key),
            "game_json": {"waterloo": "new json"}
        }

        request = self.factory.post(reverse('session_update'), data=json.dumps(data), content_type='json')
        with self.assertRaises(Http404):
            session_update(request)

    def test_session_update_unlock_success(self):
        self.session.locked = True
        self.session.save()
        data = {
            "key": str(self.session.key),
            "locked": False
        }

        request = self.factory.post(reverse('session_update'), data=json.dumps(data), content_type='json')
        response = session_update(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertFalse(self.session.locked)

    def test_session_update_game_json_and_locked(self):
        data = {
            "key": str(self.session.key),
            "game_json": {"waterloo": "new json"},
            "locked": True
        }

        request = self.factory.post(reverse('session_update'), data=json.dumps(data), content_type='json')
        response = session_update(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.game_json, {"waterloo": "new json"})
        self.assertTrue(self.session.locked)

    def test_session_update_game_json_keeps_locked_value(self):
        data = {
            "key": str(self.session.key),
            "game_json": {"waterloo": "new json"}
        }

        request = self.factory.post(reverse('session_update'), data=json.dumps(data), content_type='json')
        response = session_update(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertFalse(self.session.locked)

    def test_session_update_key_only_leaves_session_unchanged(self):
        data = {
            "key": str(self.session.key)
        }

        request = self.factory.post(reverse('session_update'), data=json.dumps(data), content_type='json')
        response = session_update(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.game_json, {"waterloo": "json"})
        self.assertFalse(self.session.locked)


class HttpMethodTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_views_reject_get_requests(self):
        for url_name, view in (
            ('session_create', session_create),
            ('session_get', session_get),
            ('session_list', session_list),
            ('session_join', session_join),
            ('session_get_archive', session_get_archive),
            ('session_archive', session_archive),
            ('session_update', session_update),
        ):
            with self.subTest(view=view.__name__):
                request = self.factory.get(reverse(url_name))
                self.assertEqual(view(request).status_code, 405)
