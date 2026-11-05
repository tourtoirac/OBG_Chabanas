import json
from datetime import UTC, datetime
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.urls import reverse

from Session import maintenance
from Session.manage_clients import ServiceUnavailable

TOURTOIRAC = 'Session.manage_clients.tourtoirac'
HAUTEFORT = 'Session.manage_clients.hautefort'
NONE = {'phase': 'none', 'starts_at': None, 'duration_minutes': 0, 'message': ''}


def answering(state):
    """A service answering every call with that state, the calls kept."""
    calls = []

    def call(method, path, body=None):
        calls.append((method, path, body))
        return state
    call.calls = calls
    return call


class BuildRequestTest(TestCase):
    def test_an_announcement_carries_the_time_of_the_start(self):
        now = datetime(2026, 10, 31, 10, 0, tzinfo=UTC)
        self.assertEqual(maintenance.build_request('announce', 5, 10, '  Mise à jour ', now=now), {
            'action': 'announce', 'starts_at': '2026-10-31T10:05:00+00:00', 'duration_minutes': 10,
            'message': 'Mise à jour'})

    def test_the_other_actions_carry_nothing_else(self):
        for action in ('start', 'cancel', 'end'):
            self.assertEqual(maintenance.build_request(action, 5, 10, 'x'), {'action': action})

    def test_badly_written_requests(self):
        for args in (('reboot',), ('announce', -1, 10), ('announce', 5, 0), ('announce', '5', 10),
                     ('announce', True, 10), ('announce', 5, 10, 'x' * 301), ('announce', 5, 10, 3)):
            with self.assertRaises(maintenance.MaintenanceRequestError):
                maintenance.build_request(*args)


class ManageMaintenanceTest(TestCase):
    def setUp(self):
        self.client.force_login(User.objects.create_user('staff', password='pw', is_staff=True))

    def post(self, body):
        return self.client.post(reverse('manage_maintenance'), json.dumps(body), content_type='application/json')

    def test_the_page_needs_a_staff_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('manage_maintenance_page')).status_code, 302)
        self.assertEqual(self.post({'action': 'start'}).status_code, 302)

    def test_the_page_is_shown_to_the_staff(self):
        response = self.client.get(reverse('manage_maintenance_page'))
        self.assertContains(response, 'Annoncer une maintenance')

    def test_the_state_of_each_service(self):
        with patch(TOURTOIRAC, answering(NONE)) as tourtoirac, patch(HAUTEFORT, answering(NONE)) as hautefort:
            data = self.client.get(reverse('manage_maintenance')).json()
        self.assertEqual(data, {'services': {'tourtoirac': NONE, 'hautefort': NONE}, 'errors': []})
        self.assertEqual(tourtoirac.calls, [('GET', '/admin/maintenance', None)])
        self.assertEqual(hautefort.calls, [('GET', '/admin/api/maintenance', None)])

    def test_an_announcement_reaches_both_services_with_the_same_start(self):
        announced = {'phase': 'announced', 'starts_at': '2026-10-31T10:05:00+00:00', 'duration_minutes': 10,
                     'message': ''}
        with patch(TOURTOIRAC, answering(announced)) as tourtoirac, patch(HAUTEFORT, answering(announced)) as hautefort:
            response = self.post({'action': 'announce', 'minutes_before': 5, 'duration_minutes': 10, 'message': ''})
        self.assertEqual(response.status_code, 200)
        [(_, path, sent)] = tourtoirac.calls
        self.assertEqual(path, '/admin/maintenance')
        self.assertEqual(hautefort.calls[0][2], sent)
        self.assertEqual(sent['action'], 'announce')
        self.assertEqual(sent['duration_minutes'], 10)

    def test_a_service_that_does_not_answer_does_not_stop_the_other(self):
        def down(method, path, body=None):
            raise ServiceUnavailable('Tourtoirac ne répond pas')
        with patch(TOURTOIRAC, down), patch(HAUTEFORT, answering({**NONE, 'phase': 'started'})) as hautefort:
            data = self.post({'action': 'start'}).json()
        self.assertEqual(hautefort.calls[0][2], {'action': 'start'})
        self.assertEqual(data['services']['tourtoirac'], {'error': 'Tourtoirac ne répond pas'})
        self.assertEqual(data['errors'], ['tourtoirac : Tourtoirac ne répond pas'])

    def test_badly_written_requests_are_refused_and_nothing_is_sent(self):
        with patch(TOURTOIRAC) as tourtoirac, patch(HAUTEFORT) as hautefort:
            self.assertEqual(self.post({'action': 'announce', 'minutes_before': 5}).status_code, 400)
            self.assertEqual(self.post({'action': 'reboot'}).status_code, 400)
            self.assertEqual(self.post(['start']).status_code, 400)
        tourtoirac.assert_not_called()
        hautefort.assert_not_called()


class MaintenanceCommandTest(TestCase):
    def test_announce(self):
        out = StringIO()
        announced = {'phase': 'announced', 'starts_at': '2026-10-31T10:05:00+00:00', 'duration_minutes': 10,
                     'message': ''}
        with patch(TOURTOIRAC, answering(announced)) as tourtoirac, patch(HAUTEFORT, answering(announced)):
            call_command('maintenance', 'announce', '--in', '5', '--duration', '10', stdout=out)
        self.assertEqual(tourtoirac.calls[0][2]['duration_minutes'], 10)
        self.assertIn('tourtoirac: announced at 2026-10-31T10:05:00+00:00, 10 min', out.getvalue())

    def test_a_service_not_reached_makes_it_fail(self):
        def down(method, path, body=None):
            raise ServiceUnavailable('Hautefort ne répond pas')
        with patch(TOURTOIRAC, answering(NONE)), patch(HAUTEFORT, down), self.assertRaises(CommandError):
            call_command('maintenance', 'end', stdout=StringIO())
