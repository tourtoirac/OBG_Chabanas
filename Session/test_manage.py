import json
from unittest.mock import patch
from urllib.parse import unquote

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from Game.models import Game, Variant
from Session.manage_clients import ServiceUnavailable
from Session.models import OccupiedGame, Player, Session

CLIENTS = 'Session.manage.manage_clients'

HAUTEFORT_LISTING = {
    'modules': [{'module': 'airforce', 'title': 'Air Force'}, {'module': 'judgedredd', 'title': 'Judge Dredd'}],
    'games': [{
        'id': 'g1', 'module': 'judgedredd', 'title': 'Judge Dredd', 'code': 'JDJDJDJD', 'status': 'playing',
        'variant': None, 'created_at': '2026-10-24T08:00:00+00:00', 'launched_at': '2026-10-24T09:00:00+00:00',
        'archived_at': None,
        'seats': [
            {'nickname': 'Bob', 'role': 'player', 'side': 'blue', 'connected': True},
            {'nickname': 'Administrateur', 'role': 'watcher', 'side': None, 'connected': True},
        ],
    }],
}


class ManageTestCase(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('staff', password='pw', is_staff=True)
        self.client.force_login(self.staff)
        self.game = Game.objects.create(name='Vietnam', display_name='Vietnam 1965')
        Variant.objects.create(game=self.game, name='first', display_name='The First Volley')
        self.session = Session.objects.create(game=self.game, code='ABCDEFGH', variant_name='first', active=True)
        Player.objects.create(session=self.session, nickname='alice', owner=True)
        Player.objects.create(session=self.session, nickname='bob')

    def post(self, name, body):
        return self.client.post(reverse(name), json.dumps(body), content_type='application/json')


class ManageAccessTest(ManageTestCase):
    def test_the_page_needs_a_staff_login(self):
        self.client.logout()
        response = self.client.get(reverse('manage_page'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_a_user_who_is_not_staff_is_sent_to_the_login(self):
        User.objects.create_user('player', password='pw')
        self.client.force_login(User.objects.get(username='player'))
        self.assertEqual(self.client.get(reverse('manage_games')).status_code, 302)

    def test_the_page_is_shown_to_the_staff(self):
        response = self.client.get(reverse('manage_page'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Administration des sessions')


class ManageListTest(ManageTestCase):
    def test_the_games_with_sessions_and_the_modules_played(self):
        Game.objects.create(name='Unplayed')
        with patch(f'{CLIENTS}.hautefort_games', return_value=HAUTEFORT_LISTING):
            data = self.client.get(reverse('manage_games')).json()
        self.assertEqual(data['games'], [
            {'id': 'hautefort:judgedredd', 'label': 'Judge Dredd'},
            {'id': f'chabanas:{self.game.id}', 'label': 'Vietnam 1965'},
        ])

    def test_hautefort_not_answering_is_a_warning(self):
        with patch(f'{CLIENTS}.hautefort_games', side_effect=ServiceUnavailable('down')):
            data = self.client.get(reverse('manage_games')).json()
        self.assertEqual([g['label'] for g in data['games']], ['Vietnam 1965'])
        self.assertEqual(len(data['warnings']), 1)

    def test_the_sessions_of_a_game_with_who_is_connected(self):
        archived = Session.objects.create(game=self.game, active=False)
        presence = {str(self.session.key): {'players': ['alice'], 'watchers': ['carol'], 'admins': 1}}
        with patch(f'{CLIENTS}.tourtoirac_presence', return_value=presence):
            data = self.client.get(reverse('manage_sessions'), {'game': f'chabanas:{self.game.id}'}).json()
        first, second = data['sessions']
        self.assertEqual(first['id'], str(self.session.key))
        self.assertEqual(first['variant'], 'The First Volley')
        self.assertEqual(first['players'], [{'nickname': 'alice', 'connected': True},
                                            {'nickname': 'bob', 'connected': False}])
        self.assertEqual(first['watchers'], ['carol'])
        self.assertTrue(first['occupied'])
        self.assertEqual(second['id'], str(archived.key))
        self.assertTrue(second['archived'])
        self.assertFalse(second['occupied'])
        self.assertFalse(second['can_access'])

    def test_tourtoirac_not_answering_leaves_the_presence_unknown(self):
        with patch(f'{CLIENTS}.tourtoirac_presence', side_effect=ServiceUnavailable('down')):
            data = self.client.get(reverse('manage_sessions'), {'game': f'chabanas:{self.game.id}'}).json()
        self.assertIsNone(data['sessions'][0]['occupied'])
        self.assertEqual(len(data['warnings']), 1)

    def test_the_games_of_a_module_without_the_administrator(self):
        with patch(f'{CLIENTS}.hautefort_games', return_value=HAUTEFORT_LISTING):
            data = self.client.get(reverse('manage_sessions'), {'game': 'hautefort:judgedredd'}).json()
        [row] = data['sessions']
        self.assertEqual(row['code'], 'JDJDJDJD')
        self.assertEqual(row['players'], [{'nickname': 'Bob', 'connected': True}])
        self.assertEqual(row['watchers'], [])
        self.assertTrue(row['occupied'])

    def test_an_unknown_game(self):
        self.assertEqual(self.client.get(reverse('manage_sessions'), {'game': 'other:1'}).status_code, 400)


class ManageArchiveTest(ManageTestCase):
    def test_a_session_nobody_is_in_is_archived_here(self):
        OccupiedGame.objects.create(code='ABCDEFGH', service='tourtoirac')
        with patch(f'{CLIENTS}.tourtoirac_close', return_value=False) as close:
            response = self.post('manage_archive', {'service': 'chabanas', 'id': str(self.session.key)})
        self.assertEqual(response.json(), {'archived': True})
        close.assert_called_once_with(str(self.session.key))
        self.session.refresh_from_db()
        self.assertFalse(self.session.active)
        self.assertEqual(self.session.code, '')
        self.assertIsNotNone(self.session.archived_at)
        self.assertFalse(OccupiedGame.objects.exists())

    def test_a_session_in_memory_is_archived_by_tourtoirac(self):
        def close(key):
            Session.objects.filter(key=key).update(active=False, code='')
            return True
        with patch(f'{CLIENTS}.tourtoirac_close', side_effect=close):
            self.post('manage_archive', {'service': 'chabanas', 'id': str(self.session.key)})
        self.session.refresh_from_db()
        self.assertFalse(self.session.active)

    def test_tourtoirac_not_answering_archives_nothing(self):
        with patch(f'{CLIENTS}.tourtoirac_close', side_effect=ServiceUnavailable('down')):
            response = self.post('manage_archive', {'service': 'chabanas', 'id': str(self.session.key)})
        self.assertEqual(response.status_code, 502)
        self.session.refresh_from_db()
        self.assertTrue(self.session.active)

    def test_a_game_of_hautefort(self):
        with patch(f'{CLIENTS}.hautefort_archive', return_value={'archived': True}) as archive:
            response = self.post('manage_archive', {'service': 'hautefort', 'id': 'g1'})
        self.assertEqual(response.json(), {'archived': True})
        archive.assert_called_once_with('g1')

    def test_the_csrf_token_is_required(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.staff)
        response = client.post(reverse('manage_archive'), json.dumps({'service': 'chabanas', 'id': 'x'}),
                               content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_a_malformed_request(self):
        self.assertEqual(self.post('manage_archive', {'service': 'other', 'id': 'x'}).status_code, 400)


class ManageDeleteTest(ManageTestCase):
    def test_everybody_is_taken_out_then_the_session_deleted(self):
        OccupiedGame.objects.create(code='ABCDEFGH', service='tourtoirac')
        with patch(f'{CLIENTS}.tourtoirac_delete', return_value=True) as delete:
            response = self.post('manage_delete', {'service': 'chabanas', 'id': str(self.session.key)})
        self.assertEqual(response.json(), {'deleted': True})
        delete.assert_called_once_with(str(self.session.key))
        self.assertFalse(Session.objects.filter(key=self.session.key).exists())
        self.assertFalse(Player.objects.exists())
        self.assertFalse(OccupiedGame.objects.exists())

    def test_tourtoirac_not_answering_deletes_nothing(self):
        with patch(f'{CLIENTS}.tourtoirac_delete', side_effect=ServiceUnavailable('down')):
            response = self.post('manage_delete', {'service': 'chabanas', 'id': str(self.session.key)})
        self.assertEqual(response.status_code, 502)
        self.assertTrue(Session.objects.filter(key=self.session.key).exists())


@override_settings(OBG_SITE_URL='/obg/')
class ManageWatchTest(ManageTestCase):
    def test_the_game_page_of_a_session_with_its_key_in_the_fragment(self):
        url = self.post('manage_access', {'service': 'chabanas', 'id': str(self.session.key)}).json()['url']
        page, _, fragment = url.partition('#admin=')
        self.assertEqual(page, '/obg/game.html?game=Vietnam')
        self.assertEqual(json.loads(unquote(fragment)), {'key': str(self.session.key), 'code': 'ABCDEFGH'})

    def test_an_archived_session_cannot_be_watched(self):
        self.session.active = False
        self.session.save()
        response = self.post('manage_access', {'service': 'chabanas', 'id': str(self.session.key)})
        self.assertEqual(response.status_code, 404)

    def test_a_game_of_hautefort_with_the_seat_in_the_fragment(self):
        seat = {'module': 'judgedredd', 'game_id': 'g1', 'token': 'tok', 'nickname': 'Administrateur',
                'role': 'watcher', 'color': None}
        with patch(f'{CLIENTS}.hautefort_watch', return_value=seat):
            url = self.post('manage_access', {'service': 'hautefort', 'id': 'g1'}).json()['url']
        page, _, fragment = url.partition('#admin=')
        self.assertEqual(page, '/obg/hautefort/judgedredd/?game=g1')
        self.assertEqual(json.loads(unquote(fragment))['token'], 'tok')


class ManageRefereedTest(ManageTestCase):
    MODULES = [
        {'module': 'airforce', 'title': 'Air Force', 'active': True, 'games': 2},
        {'module': 'judgedredd', 'title': 'Judge Dredd', 'active': False, 'games': 0},
    ]

    def test_the_page_needs_a_staff_login_and_links_the_sessions(self):
        response = self.client.get(reverse('manage_refereed_page'))
        self.assertContains(response, 'Jeux arbitrés')
        self.assertContains(response, reverse('manage_page'))
        self.client.logout()
        self.assertEqual(self.client.get(reverse('manage_refereed_page')).status_code, 302)
        self.assertEqual(self.client.get(reverse('manage_modules')).status_code, 302)

    def test_the_modules_of_hautefort_are_listed(self):
        with patch(f'{CLIENTS}.hautefort_modules', return_value=self.MODULES):
            response = self.client.get(reverse('manage_modules'))
        self.assertEqual(response.json(), {'modules': self.MODULES})

    def test_hautefort_down_is_told(self):
        with patch(f'{CLIENTS}.hautefort_modules', side_effect=ServiceUnavailable('Hautefort ne répond pas')):
            response = self.client.get(reverse('manage_modules'))
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {'error': 'Hautefort ne répond pas'})

    def test_a_module_is_turned_off(self):
        answer = {'module': 'judgedredd', 'active': False}
        with patch(f'{CLIENTS}.hautefort_set_module', return_value=answer) as set_module:
            response = self.post('manage_module_active', {'module': 'judgedredd', 'active': False})
        self.assertEqual(response.json(), answer)
        set_module.assert_called_once_with('judgedredd', False)

    def test_a_badly_written_request_is_refused(self):
        with patch(f'{CLIENTS}.hautefort_set_module') as set_module:
            for body in ({'module': 'judgedredd'}, {'module': '', 'active': True},
                         {'module': 'judgedredd', 'active': 'false'}, {'active': True}):
                self.assertEqual(self.post('manage_module_active', body).status_code, 400)
        set_module.assert_not_called()
