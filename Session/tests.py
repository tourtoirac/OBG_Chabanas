import json
import uuid

from django.shortcuts import Http404
from django.test import TestCase, RequestFactory
from django.urls import reverse

from Game.models import Game, Variant
from Session.tools import (
    generate_session_code,
    is_session_participant,
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
