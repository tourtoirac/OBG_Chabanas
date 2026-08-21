import uuid
from json import dumps, loads

from django.http import Http404
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from Waterloo.models import Waterloo
from Waterloo.tools import generate_waterloo_code
from Waterloo.views import (
    waterloo_archive,
    waterloo_create,
    waterloo_get_archive,
    waterloo_join,
    waterloo_list,
    waterloo_update,
)


class WaterlooModelTests(TestCase):
    def test_Waterloo(self):
        """
        returns the model text
        """
        waterloo = Waterloo.objects.create(
            player1_nickname="player1",
            player2_nickname="player2",
            waterloo_code = "code"
        )

        self.assertEqual(waterloo.player1_nickname, 'player1')
        self.assertEqual(waterloo.player2_nickname, 'player2')
        self.assertTrue(waterloo.active)
        print(waterloo.__str__())
        self.assertTrue("code - player1 vs player2" in waterloo.__str__())

class WaterlooCreateTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_waterloo_create_bad_method(self):
        """
        return Http "bad method" error when not POST method
        """
        request = self.factory.get(reverse('waterloo_create'))
        response = waterloo_create(request)
        self.assertEqual(response.status_code, 405)

    def test_waterloo_create_json_error(self):
        """
        return Http "bad request" error when unable to parse the JSON
        """
        request = self.factory.post(reverse('waterloo_create'), username='username')
        response = waterloo_create(request)
        self.assertEqual(response.status_code, 400)

    def test_waterloo_create_incorrect_parameters(self):
        """
        return Http "bad request" when incorrect parameters used
        """
        data = {
            "random": "some key"
        }
        request = self.factory.post(reverse('waterloo_create'), data=dumps(data), content_type='json')
        response = waterloo_create(request)
        self.assertEqual(response.status_code, 400)

    def test_waterloo_create_success(self):
        """
        return Http 201
        """
        data = {
            "nickname": "player1",
            "key": "some key"
        }
        request = self.factory.post(reverse('waterloo_create'), data=dumps(data), content_type='json')
        response = waterloo_create(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Waterloo.objects.all().count(), 1)

    def test_waterloo_failure_too_many_games(self):
        """
        return Http 409
        """
        for _ in range(20):
            Waterloo.objects.create(
                player1_nickname="player1",
                player2_nickname="player2",
                waterloo_code = generate_waterloo_code(),
                active=True
            )

        data = {
            "nickname": "player1",
            "key": "some key"
        }
        request = self.factory.post(reverse('waterloo_create'), data=dumps(data), content_type='json')
        response = waterloo_create(request)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Waterloo.objects.all().count(), 20)


class WaterlooListTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_waterloo_list_bad_method(self):
        """
        return Http "bad method" error when not POST method
        """
        request = self.factory.get(reverse('waterloo_list'))
        response = waterloo_list(request)
        self.assertEqual(response.status_code, 405)

    def test_waterloo_list_success(self):
        """
        return Http 200
        """
        game =  Waterloo.objects.create(
            player1_nickname="player1",
            player2_nickname="player2",
            waterloo_code = "code",
            active=True
        )
        data = {
            "nickname": "player1",
            "key": "some key"
        }
        request = self.factory.post(reverse('waterloo_list'), data=dumps(data), content_type='json')
        response = waterloo_list(request)
        self.assertEqual(response.status_code, 200)
        result = loads(response.content)
        self.assertEqual(len(result["games"]), 1)
        self.assertEqual(result["games"][0]["waterloo_code"], game.waterloo_code)


class WaterlooGetArchiveTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_waterloo_get_archive_bad_method(self):
        """
        return Http "bad method" error when not POST method
        """
        request = self.factory.get(reverse('waterloo_get_archive'))
        response = waterloo_get_archive(request)
        self.assertEqual(response.status_code, 405)

    def test_waterloo_get_archive_json_error(self):
        """
        return Http "bad request" error when unable to parse the JSON
        """
        request = self.factory.post(reverse('waterloo_get_archive'), username='username')
        response = waterloo_get_archive(request)
        self.assertEqual(response.status_code, 400)

    def test_waterloo_get_archive_incorrect_parameters(self):
        """
        return Http "bad request" when incorrect parameters used
        """
        data = {
            "random": "some key"
        }
        request = self.factory.post(reverse('waterloo_get_archive'), data=dumps(data), content_type='json')
        response = waterloo_get_archive(request)
        self.assertEqual(response.status_code, 400)

    def test_waterloo_get_archive_success(self):
        """
        return Http 200
        """
        game =  Waterloo.objects.create(
            player1_nickname="player1",
            player2_nickname="player2",
            waterloo_code = "code",
            active=False
        )
        data = {
            "key": str(game.waterloo_key),
        }
        request = self.factory.post(reverse('waterloo_get_archive'), data=dumps(data), content_type='json')
        response = waterloo_get_archive(request)
        self.assertEqual(response.status_code, 200)
        result = loads(response.content)
        self.assertEqual(result["key"], str(game.waterloo_key))

    def test_waterloo_get_archive_failure_unknown_game(self):
        """
        return Http 404
        """
        Waterloo.objects.create(
            player1_nickname="player1",
            player2_nickname="player2",
            waterloo_code = "code",
            active=False
        )
        data = {
            "key": str(uuid.uuid4()),
        }
        request = self.factory.post(reverse('waterloo_get_archive'), data=dumps(data), content_type='json')
        with self.assertRaises(Http404):
            waterloo_get_archive(request)


class WaterlooJoinTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_waterloo_join_bad_method(self):
        """
        return Http "bad method" error when not POST method
        """
        request = self.factory.get(reverse('waterloo_join'))
        response = waterloo_join(request)
        self.assertEqual(response.status_code, 405)

    def test_waterloo_join_json_error(self):
        """
        return Http "bad request" error when unable to parse the JSON
        """
        request = self.factory.post(reverse('waterloo_join'), username='username')
        response = waterloo_join(request)
        self.assertEqual(response.status_code, 400)

    def test_waterloo_join_incorrect_parameters(self):
        """
        return Http "bad request" when incorrect parameters used
        """
        data = {
            "random": "some key"
        }
        request = self.factory.post(reverse('waterloo_join'), data=dumps(data), content_type='json')
        response = waterloo_join(request)
        self.assertEqual(response.status_code, 400)

    def test_waterloo_join_success_new_player(self):
        """
        return Http 200
        """
        game =  Waterloo.objects.create(
            player1_nickname="player1",
            waterloo_code = "code",
            active=True
        )
        data = {
            "code": game.waterloo_code,
            "nickname": "player2",
            "key": "some key"
        }
        request = self.factory.post(reverse('waterloo_join'), data=dumps(data), content_type='json')
        response = waterloo_join(request)
        self.assertEqual(response.status_code, 200)


    def test_waterloo_join_success_rejoin(self):
        """
        return Http 200
        """
        game =  Waterloo.objects.create(
            player1_nickname="player1",
            player1_key="player1_key",
            waterloo_code = "code",
            active=True
        )
        data = {
            "code": game.waterloo_code,
            "nickname": "player1",
            "key": "player1_key",
        }
        request = self.factory.post(reverse('waterloo_join'), data=dumps(data), content_type='json')
        response = waterloo_join(request)
        self.assertEqual(response.status_code, 200)

    def test_waterloo_failure_failure_wrong_key(self):
        """
        return Http 401
        """
        game =  Waterloo.objects.create(
            player1_nickname="player1",
            player1_key="player1_key",
            waterloo_code = "code",
            active=True
        )
        data = {
            "code": game.waterloo_code,
            "nickname": "player1",
            "key": "player1_false_key",
        }
        request = self.factory.post(reverse('waterloo_join'), data=dumps(data), content_type='json')
        response = waterloo_join(request)
        self.assertEqual(response.status_code, 401)

    def test_waterloo_failure_failure_no_more_room(self):
        """
        return Http 409
        """
        game =  Waterloo.objects.create(
            player1_nickname="player1",
            player1_key="player1_key",
            player2_nickname="player2",
            player2_key="player2_key",
            waterloo_code = "code",
            active=True
        )
        data = {
            "code": game.waterloo_code,
            "nickname": "player3",
            "key": "player3_key",
        }
        request = self.factory.post(reverse('waterloo_join'), data=dumps(data), content_type='json')
        response = waterloo_join(request)
        self.assertEqual(response.status_code, 409)


class WaterlooArchiveTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_waterloo_archive_bad_method(self):
        """
        return Http "bad method" error when not POST method
        """
        request = self.factory.get(reverse('waterloo_archive'))
        response = waterloo_archive(request)
        self.assertEqual(response.status_code, 405)

    def test_waterloo_archive_json_error(self):
        """
        return Http "bad request" error when unable to parse the JSON
        """
        request = self.factory.post(reverse('waterloo_archive'), username='username')
        response = waterloo_archive(request)
        self.assertEqual(response.status_code, 400)

    def test_waterloo_archive_incorrect_parameters(self):
        """
        return Http "bad request" when incorrect parameters used
        """
        data = {
            "random": "some key"
        }
        request = self.factory.post(reverse('waterloo_archive'), data=dumps(data), content_type='json')
        response = waterloo_archive(request)
        self.assertEqual(response.status_code, 400)

    def test_waterloo_archive_success(self):
        """
        return Http 200
        """
        game =  Waterloo.objects.create(
            player1_nickname="player1",
            player2_nickname="player2",
            waterloo_code = "code",
            active=True
        )
        data = {
            "key": str(game.waterloo_key),
        }
        request = self.factory.post(reverse('waterloo_archive'), data=dumps(data), content_type='json')
        response = waterloo_archive(request)
        self.assertEqual(response.status_code, 200)


    def test_waterloo_get_archive_failure_unknown_game(self):
        """
        return Http 404
        """
        Waterloo.objects.create(
            player1_nickname="player1",
            player2_nickname="player2",
            waterloo_code = "code",
            active=True
        )
        data = {
            "key": str(uuid.uuid4()),
        }
        request = self.factory.post(reverse('waterloo_archive'), data=dumps(data), content_type='json')
        with self.assertRaises(Http404):
            waterloo_archive(request)


class WaterlooUpdateTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_waterloo_update_bad_method(self):
        """
        return Http "bad method" error when not POST method
        """
        request = self.factory.get(reverse('waterloo_update'))
        response = waterloo_update(request)
        self.assertEqual(response.status_code, 405)

    def test_waterloo_update_json_error(self):
        """
        return Http "bad request" error when unable to parse the JSON
        """
        request = self.factory.post(reverse('waterloo_update'), username='username')
        response = waterloo_update(request)
        self.assertEqual(response.status_code, 400)

    def test_waterloo_update_incorrect_parameters(self):
        """
        return Http "bad request" when incorrect parameters used
        """
        data = {
            "random": "some key"
        }
        request = self.factory.post(reverse('waterloo_update'), data=dumps(data), content_type='json')
        response = waterloo_update(request)
        self.assertEqual(response.status_code, 400)

    def test_waterloo_update_success(self):
        """
        return Http 200
        """
        game =  Waterloo.objects.create(
            player1_nickname="player1",
            player2_nickname="player2",
            waterloo_code = "code",
            active=True,
            game_json={
                "test": False
            }
        )
        data = {
            "waterloo_key": str(game.waterloo_key),
            "game_json": {
                "test": True
            },
        }
        request = self.factory.post(reverse('waterloo_update'), data=dumps(data), content_type='json')
        response = waterloo_update(request)
        self.assertEqual(response.status_code, 200)
        game.refresh_from_db()
        self.assertEqual(game.game_json, {"test": True})

    def test_waterloo_update_failure_archived_game(self):
        """
        return Http 401
        """
        game =  Waterloo.objects.create(
            player1_nickname="player1",
            player2_nickname="player2",
            waterloo_code = "code",
            active=False,
            game_json={
                "test": False
            }
        )
        data = {
            "waterloo_key": str(game.waterloo_key),
            "game_json": {
                "test": True
            },
        }
        request = self.factory.post(reverse('waterloo_update'), data=dumps(data), content_type='json')
        response = waterloo_update(request)
        self.assertEqual(response.status_code, 401)

    def test_waterloo_update_failure_unknown_game(self):
        """
        return Http 404
        """
        Waterloo.objects.create(
            player1_nickname="player1",
            player2_nickname="player2",
            waterloo_code = "code",
            active=True,
            game_json={
                "test": False
            }
        )
        data = {
            "waterloo_key": str(uuid.uuid4()),
            "game_json": {
                "test": True
            },
        }
        request = self.factory.post(reverse('waterloo_update'), data=dumps(data), content_type='json')
        with self.assertRaises(Http404):
            waterloo_update(request)
