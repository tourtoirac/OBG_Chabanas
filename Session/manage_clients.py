"""
What the administration of OBG (the /manage/ pages, Session/manage.py) asks the
services holding the live connections, Chabanas only storing the sessions:
Tourtoirac for the sessions of Chabanas (Tourtoirac/admin_api.py), Hautefort for
its own games (Hautefort/hautefort/admin.py). Both are called on the Docker
network with the secret they share with Chabanas (settings.OBG_ADMIN_SECRET).
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

# seconds: closing a session makes Tourtoirac call Chabanas twice meanwhile
TIMEOUT = 15


class ServiceUnavailable(Exception):
    """A service did not answer, or refused: the administrator is told so."""


def _call(base: str, method: str, path: str, body: dict | None = None) -> dict:
    """
    One request to a service.
    :return: the JSON answer
    :raise ServiceUnavailable: no answer, or an error status
    """
    request = urllib.request.Request(
        base.rstrip('/') + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={'Content-Type': 'application/json', 'X-OBG-Admin-Secret': settings.OBG_ADMIN_SECRET},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read() or b'{}')
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors='replace')[:300]
        logger.error("%s %s%s answered %s: %s", method, base, path, error.code, detail)
        raise ServiceUnavailable(f"{base} a répondu {error.code} : {detail}") from error
    except (urllib.error.URLError, OSError, ValueError) as error:
        logger.error("%s %s%s failed: %s", method, base, path, error)
        raise ServiceUnavailable(f"{base} ne répond pas") from error


def tourtoirac(method: str, path: str, body: dict | None = None) -> dict:
    return _call(settings.OBG_TOURTOIRAC_ADMIN_URL, method, path, body)


def hautefort(method: str, path: str, body: dict | None = None) -> dict:
    return _call(settings.OBG_HAUTEFORT_URL, method, path, body)


def tourtoirac_presence() -> dict:
    """:return: who is connected to each session Tourtoirac holds in memory, by session key"""
    return {entry['key']: entry for entry in tourtoirac('GET', '/admin/presence').get('sessions', [])}


def tourtoirac_close(key: str) -> bool:
    """:return: False when the session is not in memory: Chabanas archives it alone"""
    return bool(tourtoirac('POST', '/admin/close', {'key': key}).get('handled'))


def tourtoirac_delete(key: str) -> bool:
    """Everybody in the session is told and taken out of it."""
    return bool(tourtoirac('POST', '/admin/delete', {'key': key}).get('handled'))


def hautefort_games() -> dict:
    """:return: {modules: [{module, title}], games: [...]}, every game of every module"""
    return hautefort('GET', '/admin/api/games')


def hautefort_archive(game_id: str) -> dict:
    return hautefort('POST', f'/admin/api/games/{game_id}/archive')


def hautefort_delete(game_id: str) -> dict:
    return hautefort('DELETE', f'/admin/api/games/{game_id}')


def hautefort_watch(game_id: str) -> dict:
    """:return: a watcher seat for the administrator: {module, game_id, token, nickname, role, ...}"""
    return hautefort('POST', f'/admin/api/games/{game_id}/watch')


def hautefort_modules() -> list:
    """:return: every module of Hautefort: [{module, title, active, prototype_key, games}]"""
    return hautefort('GET', '/admin/api/modules').get('modules', [])


def hautefort_set_module(module: str, active: bool) -> dict:
    """Turns a module on or off: an inactive one is offered by no lobby and creates no game."""
    return hautefort('POST', f'/admin/api/modules/{module}', {'active': active})


def hautefort_set_prototype(module: str, prototype_key: str) -> dict:
    """Puts a module in prototyping (empty key: public again): its key is asked to create or join a game."""
    return hautefort('POST', f'/admin/api/modules/{module}/prototype', {'prototype_key': prototype_key})
