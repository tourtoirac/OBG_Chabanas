"""
Maintenance of the site: announced to the players and watchers of every game,
started, cancelled or ended. Chabanas only relays it to the two services
holding the live connections, which keep it in memory and start on their own
at the time announced (Tourtoirac/maintenance.py, Hautefort/hautefort/maintenance.py):

    announce  every page shows a countdown; nobody creates or joins a game any
              more, only a player comes back to a seat of their game
    start     every game is stored and every connection closed; the pages keep
              reconnecting until the end (at once: no wait for the time announced)
    cancel    the announcement is withdrawn (ends one already started)
    end       connections accepted again: the pages come back to their games

Used by the page manage/maintenance/ (Session/manage.py) and by
`manage.py maintenance` (Session/management/commands/maintenance.py), which
deploy.sh runs on the server around a deployment.
"""
from datetime import UTC, datetime, timedelta

from Session import manage_clients
from Session.manage_clients import ServiceUnavailable

ACTIONS = ('announce', 'start', 'cancel', 'end')
# the bounds of an announcement, the same as the services check
DELAY_MAX = 24 * 60
DURATION_MAX = 24 * 60
MESSAGE_MAX = 300

# the services, in the order they are asked
SERVICES = (
    ('tourtoirac', manage_clients.tourtoirac_maintenance),
    ('hautefort', manage_clients.hautefort_maintenance),
)


class MaintenanceRequestError(ValueError):
    """An announcement badly written: nothing is sent."""


def build_request(action: str, minutes_before=None, duration_minutes=None, message='', now=None) -> dict:
    """
    :param minutes_before: announce only, the minutes until the start (0: at once)
    :param duration_minutes: announce only, the duration announced to the players
    :return: what the services are sent
    :raise MaintenanceRequestError: an action or a field badly written
    """
    if action not in ACTIONS:
        raise MaintenanceRequestError(f"Action inconnue : {action}")
    if action != 'announce':
        return {'action': action}
    for name, value, low, high in (('minutes_before', minutes_before, 0, DELAY_MAX),
                                   ('duration_minutes', duration_minutes, 1, DURATION_MAX)):
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise MaintenanceRequestError(f"{name} doit être un nombre de minutes de {low} à {high}")
    message = '' if message is None else message
    if not isinstance(message, str) or len(message.strip()) > MESSAGE_MAX:
        raise MaintenanceRequestError(f"Le message fait au plus {MESSAGE_MAX} caractères")
    starts_at = (now or datetime.now(UTC)) + timedelta(minutes=minutes_before)
    return {'action': 'announce', 'starts_at': starts_at.isoformat(timespec='seconds'),
            'duration_minutes': duration_minutes, 'message': message.strip()}


def _each(body: dict | None) -> dict:
    """
    Every service, even when one does not answer: a maintenance must reach the
    ones that do.
    :return: {service: its state, or {'error': why}}
    """
    states = {}
    for name, call in SERVICES:
        try:
            states[name] = call(body)
        except ServiceUnavailable as error:
            states[name] = {'error': str(error)}
    return states


def status() -> dict:
    """:return: {service: {phase, starts_at, duration_minutes, message} or {'error': ...}}"""
    return _each(None)


def apply(action: str, minutes_before=None, duration_minutes=None, message='') -> dict:
    """
    Sends the action to every service.
    :return: {service: its state after it, or {'error': ...}}
    :raise MaintenanceRequestError: an action or a field badly written
    """
    return _each(build_request(action, minutes_before, duration_minutes, message))


def failures(states: dict) -> list:
    """:return: the services that did not answer, with why"""
    return [f"{name} : {state['error']}" for name, state in states.items() if 'error' in state]
