import json
import uuid

from datetime import datetime, timedelta, UTC
from unittest.mock import patch

from django.contrib import admin
from django.shortcuts import Http404
from django.test import TestCase, RequestFactory
from django.urls import reverse

from Game.models import Game, Variant
from Session.admin import HasCodeFilter, SessionAdmin
from Session.tools import (
    generate_session_code,
    is_session_participant,
    return_player_json,
    return_session_json,
)
from Session.models import OccupiedGame, ReservedCode, Session, Player
from Session.views import (session_create, session_get, session_list, session_archive, session_get_archive,
                           session_join, session_launch, session_occupy, session_release_code,
                           session_reserve_code, session_sync_occupancy, session_update, session_vacate)


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

    @patch('Session.tools.secrets.choice', side_effect=['A'] * 8 + ['B'] * 8)
    def test_generate_session_code_skips_a_reserved_code(self, mock_choice):
        ReservedCode.objects.create(code='AAAAAAAA', owner='hautefort')

        self.assertEqual(generate_session_code(), 'BBBBBBBB')

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

    def test_return_session_json_names_the_game_or_the_variant_played(self):
        game = Game.objects.create(name="waterloo", display_name="Waterloo 1815")
        Variant.objects.create(game=game, name="grouchy", display_name="Grouchy arrive")
        Variant.objects.create(game=game, name="plain")

        def shown(variant_name):
            session = Session.objects.create(game=game, variant_name=variant_name)
            return return_session_json(session)["display_name"]

        self.assertEqual(shown("default"), "Waterloo 1815")
        self.assertEqual(shown("grouchy"), "Grouchy arrive")
        # an empty display_name falls back on the name
        self.assertEqual(shown("plain"), "plain")
        # a variant since deleted falls back on the game
        self.assertEqual(shown("gone"), "Waterloo 1815")

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
        self.assertEqual(data, {"nickname": "P1", "owner": True, "nationality": None})

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
        self.assertEqual(data, {"nickname": "P1", "owner": True, "nationality": None, "key": "K1"})

class SessionCreateTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(
            name="waterloo",
            max_players=2,
            max_watchers=10,
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
        self.assertEqual(session.game_json, {'game': 'waterloo', 'options': {}})

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
        self.assertEqual(session.game_json, {'variant': 'waterloo solo', 'options': {}})

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

    def test_session_create_success_without_active_session_limit(self):
        for i in range(15):
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
        self.assertEqual(response.status_code, 201)

    @patch.dict('Session.tools.PARAMS_EXT', {"MAX_ACTIVE_SESSIONS": 2})
    def test_session_create_refused_when_the_platform_is_full(self):
        # every game with players in it counts, whatever its service
        OccupiedGame.objects.create(code="S1", service="tourtoirac")
        OccupiedGame.objects.create(code="H1", service="hautefort")
        data = {"game_name": "waterloo", "nickname": "Chins", "key": "123456789"}

        request = self.factory.post(reverse('session_create'), data=json.dumps(data), content_type='json')
        response = session_create(request)

        self.assertEqual(response.status_code, 409)
        self.assertFalse(Session.objects.filter(active=True).exists())

    @patch.dict('Session.tools.PARAMS_EXT', {"MAX_ACTIVE_SESSIONS": 2})
    def test_session_create_success_below_the_platform_limit(self):
        # active sessions and reserved codes nobody plays in do not count
        Session.objects.create(game=self.game, code="S1", active=True)
        ReservedCode.objects.create(code="H1", owner="hautefort")
        OccupiedGame.objects.create(code="S1", service="tourtoirac")
        data = {"game_name": "waterloo", "nickname": "Chins", "key": "123456789"}

        request = self.factory.post(reverse('session_create'), data=json.dumps(data), content_type='json')
        self.assertEqual(session_create(request).status_code, 201)

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
        self.assertFalse(session.started)

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

    def test_session_create_one_seat_session_is_started(self):
        data = {
            "game_name": "waterloo",
            "nickname": "Chins",
            "key": "123456789",
            "session_max_players": 1,
        }

        request = self.factory.post(reverse('session_create'), data=json.dumps(data), content_type='json')
        response = session_create(request)
        self.assertEqual(response.status_code, 201)
        json_response = json.loads(response.content)
        session = Session.objects.get(key=json_response["session_key"])
        self.assertTrue(session.started)

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
        self.assertEqual(session.game_json, {'variant': 'waterloo duo', 'options': {}})

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
        self.assertEqual(session_data["players"], [{"nickname": "P1", "owner": True, "nationality": None}])

class SessionListTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(
            name="waterloo",
            max_players=2,
            max_watchers=10,
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

    def test_session_list_without_names_lists_active_games(self):
        Game.objects.create(name="diplomacy", active=True)
        Game.objects.create(name="vietnam", active=False)
        data = {
        }

        request = self.factory.post(reverse('session_list'), data=json.dumps(data), content_type='json')
        response = session_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(sorted(response_content["sessions"]), ['diplomacy', 'waterloo'])
        self.assertEqual(len(response_content["sessions"]["waterloo"]), 1)
        self.assertEqual(response_content["sessions"]["diplomacy"], [])

    def test_session_list_counts_the_games_in_progress_of_the_platform(self):
        ReservedCode.objects.create(code='AAAAAAAA', owner='hautefort')
        ReservedCode.objects.create(code='BBBBBBBB', owner='hautefort')
        OccupiedGame.objects.create(code='AAAAAAAA', service='hautefort')

        request = self.factory.post(reverse('session_list'), data=json.dumps({}), content_type='json')
        content = json.loads(session_list(request).content)

        # only the game with players in it
        self.assertEqual(content["active_games"], 1)
        self.assertEqual(content["max_active_games"], 20)

    def test_session_list_rejects_a_non_list(self):
        data = {
            "game_name_list": "waterloo",
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

    def test_session_list_archives_a_session_never_launched_for_15_days(self):
        Session.objects.filter(pk=self.session.pk).update(
            created_at=datetime.now(UTC) - timedelta(days=16),
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
        self.assertIsNotNone(self.session.archived_at)

    def test_session_list_archives_a_session_not_launched_for_15_days(self):
        self.session.code = '1234'
        self.session.save()
        Session.objects.filter(pk=self.session.pk).update(
            created_at=datetime.now(UTC) - timedelta(days=60),
            launched_at=datetime.now(UTC) - timedelta(days=16),
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

    def test_session_list_keeps_a_session_launched_recently(self):
        self.session.code = '1234'
        self.session.save()
        Session.objects.filter(pk=self.session.pk).update(
            created_at=datetime.now(UTC) - timedelta(days=60),
            launched_at=datetime.now(UTC) - timedelta(days=14),
        )
        data = {
            "game_name_list": ['waterloo'],
        }

        request = self.factory.post(reverse('session_list'), data=json.dumps(data), content_type='json')
        response = session_list(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertTrue(self.session.active)
        self.assertEqual(self.session.code, '1234')

    def test_session_list_deletes_sessions_archived_for_180_days(self):
        self.session.active = False
        self.session.save()
        Session.objects.filter(pk=self.session.pk).update(
            archived_at=datetime.now(UTC) - timedelta(days=181),
        )
        recent = Session.objects.create(
            game=self.game,
            active=False,
            archived_at=datetime.now(UTC) - timedelta(days=179),
        )

        request = self.factory.post(reverse('session_list'), data=json.dumps({}), content_type='json')
        response = session_list(request)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Session.objects.filter(pk=self.session.pk).exists())
        self.assertFalse(Player.objects.filter(session_id=self.session.pk).exists())
        self.assertTrue(Session.objects.filter(pk=recent.pk).exists())

    def test_session_list_keeps_recent_sessions_active(self):
        self.session.code = '1234'
        self.session.save()
        Session.objects.filter(pk=self.session.pk).update(
            created_at=datetime.now(UTC) - timedelta(days=14),
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

    def test_session_list_lists_inactive_game_with_active_variant(self):
        # the lobby asks without game_name_list: an inactive game keeps its tab
        # as long as one of its variants is active
        Variant.objects.create(game=self.game, name="grouchy", active=True)
        self.game.active = False
        self.game.save()

        request = self.factory.post(reverse('session_list'), data=json.dumps({}), content_type='json')
        response = session_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertEqual(len(response_content["sessions"]['waterloo']), 1)

    def test_session_list_excludes_inactive_game_with_inactive_variants(self):
        Variant.objects.create(game=self.game, name="grouchy", active=False)
        self.game.active = False
        self.game.save()

        request = self.factory.post(reverse('session_list'), data=json.dumps({}), content_type='json')
        response = session_list(request)
        self.assertEqual(response.status_code, 200)
        response_content = json.loads(response.content)
        self.assertNotIn('waterloo', response_content["sessions"])

class SessionJoinTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(
            name="waterloo",
            max_players=2,
            max_watchers=10,
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

    def test_session_join_watcher_success_started_session(self):
        self.session.started = True
        self.session.save()
        data = {
            "session_code": 'code1',
            "nickname": "S1",
            "role": "watcher",
            "access_key": "SK1",
        }

        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)

        self.assertEqual(response.status_code, 200)
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

    def test_session_join_failure_started_session(self):
        self.session.started = True
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

    def test_session_join_success_returning_player_on_started_session(self):
        self.session.started = True
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

    def test_session_join_success_returning_player_when_started_and_full(self):
        self.session.started = True
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

    def test_session_join_last_seat_starts_the_session(self):
        data = {
            "session_code": 'code1',
            "nickname": "P2",
            "key": "K2",
            "access_key": "SK1"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)["started"])
        self.session.refresh_from_db()
        self.assertTrue(self.session.started)

    def test_session_join_free_seat_left_does_not_start_the_session(self):
        self.session.max_players = 3
        self.session.save()
        data = {
            "session_code": 'code1',
            "nickname": "P2",
            "key": "K2",
            "access_key": "SK1"
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(json.loads(response.content)["started"])
        self.session.refresh_from_db()
        self.assertFalse(self.session.started)

    def test_session_join_watcher_does_not_start_the_session(self):
        self.session.max_players = 1
        self.session.save()
        Player.objects.filter(session=self.session).delete()
        data = {
            "session_code": 'code1',
            "nickname": "S1",
            "role": "watcher",
            "access_key": "SK1",
        }
        request = self.factory.post(reverse('session_join'), data=json.dumps(data), content_type='json')
        response = session_join(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertFalse(self.session.started)


class SessionGetArchiveTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(
            name="waterloo",
            max_players=2,
            max_watchers=10,
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
        self.assertIsNotNone(self.session.archived_at)

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

    def test_session_archive_keeps_the_players(self):
        """
        Archiving a game does not unseat anybody: the players stay attached to
        the session, so the archived game still tells who was at the table.
        """
        Player.objects.create(
            session=self.session,
            nickname="P2",
            key="K2",
            owner=False,
        )
        data = {
            "key": str(self.session.key),
        }

        request = self.factory.post(reverse('session_archive'), data=json.dumps(data), content_type='json')
        self.assertEqual(session_archive(request).status_code, 200)

        self.assertEqual(
            sorted(player.nickname for player in Player.objects.filter(session=self.session)),
            ["P1", "P2"],
        )

    def test_an_archived_session_still_lists_its_players(self):
        data = {"key": str(self.session.key)}
        request = self.factory.post(reverse('session_archive'), data=json.dumps(data), content_type='json')
        session_archive(request)

        request = self.factory.post(reverse('session_get_archive'), data=json.dumps(data), content_type='json')
        response = session_get_archive(request)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertFalse(content["active"])
        self.assertEqual(
            content["players"],
            [{"nickname": "P1", "owner": True, "nationality": None}],
        )

    def test_an_archived_session_can_no_longer_be_joined(self):
        data = {"key": str(self.session.key)}
        request = self.factory.post(reverse('session_archive'), data=json.dumps(data), content_type='json')
        session_archive(request)
        self.session.refresh_from_db()

        request = self.factory.post(reverse('session_join'), data=json.dumps({
            "session_code": self.session.code,
            "nickname": "P2",
            "key": "",
            "access_key": self.session.access_key,
        }), content_type='json')

        with self.assertRaises(Http404):
            session_join(request)

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


class SessionLaunchTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(name="waterloo", active=True)
        self.session = Session.objects.create(game=self.game, code='1234', active=True)

    def launch(self, key):
        request = self.factory.post(
            reverse('session_launch'), data=json.dumps({"key": key}), content_type='json'
        )
        return session_launch(request)

    def test_session_launch_records_the_date(self):
        before = datetime.now(UTC)
        response = self.launch(str(self.session.key))
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertGreaterEqual(self.session.launched_at, before)
        self.assertEqual(json.loads(response.content)["launched_at"], self.session.launched_at.isoformat())

    def test_session_launch_unknown_session(self):
        with self.assertRaises(Http404):
            self.launch(str(uuid.uuid4()))

    def test_session_launch_archived_session(self):
        self.session.active = False
        self.session.save()
        with self.assertRaises(Http404):
            self.launch(str(self.session.key))

    def test_session_launch_without_key(self):
        request = self.factory.post(reverse('session_launch'), data=json.dumps({}), content_type='json')
        self.assertEqual(session_launch(request).status_code, 400)


class ReservedCodeTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def post(self, view, url_name, data):
        request = self.factory.post(reverse(url_name), data=json.dumps(data), content_type='json')
        return view(request)

    @patch('Session.tools.secrets.choice', side_effect=['A'] * 8 + ['B'] * 8)
    def test_reserve_code_skips_the_codes_of_active_sessions(self, mock_choice):
        game = Game.objects.create(name="waterloo")
        Session.objects.create(game=game, code='AAAAAAAA', active=True)

        response = self.post(session_reserve_code, 'session_reserve_code', {"owner": "hautefort"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(json.loads(response.content), {"code": "BBBBBBBB"})
        self.assertEqual(ReservedCode.objects.get(code='BBBBBBBB').owner, 'hautefort')

    @patch.dict('Session.tools.PARAMS_EXT', {"MAX_ACTIVE_SESSIONS": 1})
    def test_reserve_code_refused_when_the_platform_is_full(self):
        ReservedCode.objects.create(code='AAAAAAAA', owner='hautefort')
        OccupiedGame.objects.create(code='AAAAAAAA', service='hautefort')

        response = self.post(session_reserve_code, 'session_reserve_code', {"owner": "hautefort"})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(ReservedCode.objects.count(), 1)

    def test_reserve_code_needs_an_owner(self):
        for data in ({}, {"owner": ""}, {"owner": 3}):
            with self.subTest(data=data):
                self.assertEqual(self.post(session_reserve_code, 'session_reserve_code', data).status_code, 400)

    def test_release_code(self):
        ReservedCode.objects.create(code='AAAAAAAA', owner='hautefort')

        response = self.post(session_release_code, 'session_release_code', {"code": "AAAAAAAA"})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ReservedCode.objects.exists())

    def test_release_an_unknown_code(self):
        response = self.post(session_release_code, 'session_release_code', {"code": "AAAAAAAA"})
        self.assertEqual(response.status_code, 404)

    def test_release_code_without_code(self):
        self.assertEqual(self.post(session_release_code, 'session_release_code', {}).status_code, 400)


class OccupancyTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(name="waterloo")
        for code in ("S1", "S2"):
            Session.objects.create(game=self.game, code=code, active=True)
        ReservedCode.objects.create(code="H1", owner="hautefort")

    def post(self, view, url_name, data):
        request = self.factory.post(reverse(url_name), data=json.dumps(data), content_type='json')
        return view(request)

    def occupy(self, code, service="tourtoirac"):
        return self.post(session_occupy, 'session_occupy', {"code": code, "service": service})

    @patch.dict('Session.tools.PARAMS_EXT', {"MAX_ACTIVE_SESSIONS": 2})
    def test_occupy_up_to_the_limit_of_the_platform(self):
        self.assertEqual(self.occupy("S1").status_code, 200)
        self.assertEqual(self.occupy("H1", "hautefort").status_code, 200)
        # a game already occupied takes one more player
        self.assertEqual(self.occupy("S1").status_code, 200)
        # an empty one is refused
        self.assertEqual(self.occupy("S2").status_code, 409)
        self.assertEqual(sorted(OccupiedGame.objects.values_list("code", flat=True)), ["H1", "S1"])

    def test_occupy_an_unknown_code(self):
        Session.objects.create(game=self.game, code="OLD", active=False)
        for code in ("NOPE", "OLD"):
            with self.subTest(code=code):
                self.assertEqual(self.occupy(code).status_code, 404)
        self.assertFalse(OccupiedGame.objects.exists())

    def test_occupy_needs_a_code_and_a_service(self):
        for data in ({"code": "S1"}, {"service": "tourtoirac"}, {"code": "", "service": "tourtoirac"}):
            with self.subTest(data=data):
                self.assertEqual(self.post(session_occupy, 'session_occupy', data).status_code, 400)

    @patch.dict('Session.tools.PARAMS_EXT', {"MAX_ACTIVE_SESSIONS": 1})
    def test_vacate_frees_a_place(self):
        self.occupy("S1")
        response = self.post(session_vacate, 'session_vacate', {"code": "S1"})
        self.assertEqual(json.loads(response.content), {"vacated": 1})
        self.assertEqual(self.occupy("S2").status_code, 200)

    def test_vacate_every_game_of_a_service(self):
        self.occupy("S1")
        self.occupy("S2")
        self.occupy("H1", "hautefort")
        response = self.post(session_vacate, 'session_vacate', {"service": "tourtoirac"})
        self.assertEqual(json.loads(response.content), {"vacated": 2})
        self.assertEqual(list(OccupiedGame.objects.values_list("code", flat=True)), ["H1"])

    @patch.dict('Session.tools.PARAMS_EXT', {"MAX_ACTIVE_SESSIONS": 1})
    def test_sync_replaces_the_games_of_a_service(self):
        self.occupy("S1")
        OccupiedGame.objects.create(code="H1", service="hautefort")
        # beyond the limit: a sync says what is, it is never refused
        response = self.post(session_sync_occupancy, 'session_sync_occupancy',
                             {"service": "tourtoirac", "codes": ["S2", "NOPE", "H1"]})
        self.assertEqual(json.loads(response.content), {"added": ["S2"], "removed": ["S1"]})
        # S1 left, S2 came, an unknown code is ignored, H1 stays Hautefort's
        self.assertEqual(
            sorted(OccupiedGame.objects.values_list("code", "service")),
            [("H1", "hautefort"), ("S2", "tourtoirac")],
        )

    def test_sync_of_a_right_database_changes_nothing(self):
        self.occupy("S1")
        response = self.post(session_sync_occupancy, 'session_sync_occupancy',
                             {"service": "tourtoirac", "codes": ["S1"]})
        self.assertEqual(json.loads(response.content), {"added": [], "removed": []})

    def test_sync_with_no_game_frees_the_service(self):
        self.occupy("S1")
        self.post(session_sync_occupancy, 'session_sync_occupancy', {"service": "tourtoirac", "codes": []})
        self.assertFalse(OccupiedGame.objects.exists())

    def test_sync_needs_a_service_and_a_list(self):
        for data in ({"codes": []}, {"service": "tourtoirac"}, {"service": "tourtoirac", "codes": "S1"}):
            with self.subTest(data=data):
                self.assertEqual(
                    self.post(session_sync_occupancy, 'session_sync_occupancy', data).status_code, 400)

    def test_vacate_needs_a_code_or_a_service(self):
        self.assertEqual(self.post(session_vacate, 'session_vacate', {}).status_code, 400)

    def test_an_archived_or_released_game_is_no_longer_occupied(self):
        self.occupy("S1")
        self.occupy("H1", "hautefort")
        session = Session.objects.get(code="S1")
        self.post(session_archive, 'session_archive', {"key": str(session.key)})
        self.post(session_release_code, 'session_release_code', {"code": "H1"})
        self.assertFalse(OccupiedGame.objects.exists())


class SessionUpdateTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(
            name="waterloo",
            max_players=2,
            max_watchers=10,
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
            started=False,
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

    def test_session_update_started_success(self):
        data = {
            "key": str(self.session.key),
            "started": True
        }

        request = self.factory.post(reverse('session_update'), data=json.dumps(data), content_type='json')
        response = session_update(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertTrue(self.session.started)

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

    def test_session_update_failure_cannot_unstart(self):
        self.session.started = True
        self.session.save()
        data = {
            "key": str(self.session.key),
            "started": False
        }

        request = self.factory.post(reverse('session_update'), data=json.dumps(data), content_type='json')
        response = session_update(request)
        self.assertEqual(response.status_code, 400)
        self.session.refresh_from_db()
        self.assertTrue(self.session.started)

    def test_session_update_game_json_and_started(self):
        data = {
            "key": str(self.session.key),
            "game_json": {"waterloo": "new json"},
            "started": True
        }

        request = self.factory.post(reverse('session_update'), data=json.dumps(data), content_type='json')
        response = session_update(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.game_json, {"waterloo": "new json"})
        self.assertTrue(self.session.started)

    def test_session_update_game_json_keeps_started_value(self):
        data = {
            "key": str(self.session.key),
            "game_json": {"waterloo": "new json"}
        }

        request = self.factory.post(reverse('session_update'), data=json.dumps(data), content_type='json')
        response = session_update(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertFalse(self.session.started)

    def test_session_update_key_only_leaves_session_unchanged(self):
        data = {
            "key": str(self.session.key)
        }

        request = self.factory.post(reverse('session_update'), data=json.dumps(data), content_type='json')
        response = session_update(request)
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.game_json, {"waterloo": "json"})
        self.assertFalse(self.session.started)


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
            ('session_launch', session_launch),
            ('session_reserve_code', session_reserve_code),
            ('session_occupy', session_occupy),
            ('session_vacate', session_vacate),
            ('session_sync_occupancy', session_sync_occupancy),
            ('session_release_code', session_release_code),
            ('session_update', session_update),
        ):
            with self.subTest(view=view.__name__):
                request = self.factory.get(reverse(url_name))
                self.assertEqual(view(request).status_code, 405)


class NationalityTests(TestCase):
    """
    A game may declare nationalities in the options of its game_json: every new player then
    chooses one of them, and several players may share the same one.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.game = Game.objects.create(
            name="vietnam",
            max_players=3,
            options={"nationalities": ["US", "NVA"]},
            active=True,
        )
        self.plain_game = Game.objects.create(
            name="waterloo",
            max_players=2,
            game_json={"game": "waterloo"},
            active=True,
        )

    def post(self, view, url_name, data):
        request = self.factory.post(reverse(url_name), data=json.dumps(data), content_type='json')
        return view(request)

    def create(self, **extra):
        return self.post(session_create, 'session_create', {"game_name": "vietnam", "nickname": "P1", **extra})

    def join(self, code, nickname, **extra):
        return self.post(session_join, 'session_join', {"session_code": code, "nickname": nickname, **extra})

    def created_session(self):
        response = self.create(nationality="US", key="K1")
        return Session.objects.get(key=json.loads(response.content)["session_key"])

    def test_create_replaces_the_options_of_the_game_json(self):
        # an "options" block left in the game_json is not what the session gets
        self.game.game_json = {"fixed": [], "options": {"nationalities": ["old"]}}
        self.game.save()

        session = self.created_session()

        self.assertEqual(session.game_json, {"fixed": [], "options": {"nationalities": ["US", "NVA"]}})
        self.game.refresh_from_db()
        self.assertEqual(self.game.game_json["options"], {"nationalities": ["old"]})

    def test_create_from_a_variant_uses_the_options_of_the_variant(self):
        Variant.objects.create(game=self.game, name="short", game_json={"fixed": [1]}, options={"screen_capture": False})

        response = self.create(variant_name="short", key="K1")

        session = Session.objects.get(key=json.loads(response.content)["session_key"])
        self.assertEqual(session.game_json, {"fixed": [1], "options": {"screen_capture": False}})

    def test_create_stores_the_nationality_of_the_owner(self):
        session = self.created_session()
        self.assertEqual(Player.objects.get(session=session).nationality, "US")

    def test_create_refuses_a_missing_nationality(self):
        response = self.create()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(Session.objects.count(), 0)

    def test_create_refuses_an_unknown_nationality(self):
        response = self.create(nationality="France")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(Session.objects.count(), 0)

    def test_create_ignores_the_nationality_when_the_game_has_none(self):
        response = self.post(
            session_create, 'session_create',
            {"game_name": "waterloo", "nickname": "P1", "nationality": "US"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Player.objects.get(nickname="P1").nationality, "")

    def test_join_stores_the_nationality_of_a_new_player(self):
        session = self.created_session()
        response = self.join(session.code, "P2", nationality="NVA")
        self.assertEqual(response.status_code, 200)
        players = {player["nickname"]: player["nationality"] for player in json.loads(response.content)["players"]}
        self.assertEqual(players, {"P1": "US", "P2": "NVA"})

    def test_two_players_may_share_a_nationality(self):
        session = self.created_session()
        response = self.join(session.code, "P2", nationality="US")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Player.objects.filter(session=session, nationality="US").count(), 2)

    def test_join_refuses_a_new_player_without_a_valid_nationality(self):
        session = self.created_session()
        for extra in ({}, {"nationality": "France"}, {"nationality": None}, {"nationality": ["US"]}):
            with self.subTest(extra=extra):
                response = self.join(session.code, "P2", **extra)
                self.assertEqual(response.status_code, 422)
        self.assertEqual(Player.objects.filter(session=session).count(), 1)

    def test_a_returning_player_keeps_the_nationality_of_their_seat(self):
        session = self.created_session()
        response = self.join(session.code, "P1", key="K1", nationality="NVA")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Player.objects.get(session=session, nickname="P1").nationality, "US")

    def test_a_watcher_needs_no_nationality(self):
        session = self.created_session()
        response = self.join(session.code, "W1", role="watcher")
        self.assertEqual(response.status_code, 200)

    def test_the_session_json_lists_the_nationalities_of_its_game(self):
        session = self.created_session()
        self.assertEqual(return_session_json(session)["nationalities"], ["US", "NVA"])
        plain = Session.objects.create(game=self.plain_game, game_json=self.plain_game.game_json)
        self.assertEqual(return_session_json(plain)["nationalities"], [])


class SessionAdminTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        game = Game.objects.create(name="waterloo")
        self.with_code = Session.objects.create(game=game, code="ABCD1234", active=True)
        self.without_code = Session.objects.create(game=game, code="", active=False)

    def filtered(self, value):
        request = self.factory.get("/", {"has_code": value} if value else {})
        params = dict(request.GET.lists())
        sessions_filter = HasCodeFilter(request, params, Session, SessionAdmin(Session, admin.site))
        return set(sessions_filter.queryset(request, Session.objects.all()))

    def test_the_code_filter_keeps_the_sessions_with_a_code(self):
        self.assertEqual(self.filtered("yes"), {self.with_code})

    def test_the_code_filter_keeps_the_sessions_without_a_code(self):
        self.assertEqual(self.filtered("no"), {self.without_code})

    def test_without_the_code_filter_every_session_is_listed(self):
        self.assertEqual(self.filtered(None), {self.with_code, self.without_code})
