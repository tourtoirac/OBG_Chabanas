"""
Administration of OBG: the /manage/ pages, for the staff of the Django admin
(same login). Every game with sessions, archived or not, whatever the service
playing it: the sessions of Chabanas (played on Tourtoirac) and the games of
Hautefort (one entry per module). For each session: who is connected, its
code, its game and variant, its last launch, its players; and three actions:
watch it (even when it refuses watchers), archive it (its code freed, the
players turned into watchers) and delete it (everybody taken out of it).

The page manage/refereed/ lists the refereed games (the modules of
Hautefort) and turns each of them on or off: an inactive one is offered by no
lobby and creates no game; its games already there go on.

A game of the drop-down list is named "chabanas:<Game.id>" or
"hautefort:<module>"; a session "chabanas" + its key, or "hautefort" + the id
of the game.
"""
import json
import logging
from datetime import UTC, datetime
from urllib.parse import quote

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from Chabanas.params_ext import BAD_REQUEST
from Game.models import Game, Variant
from Session import manage_clients
from Session.manage_clients import ServiceUnavailable
from Session.models import Session
from Session.tools import drop_stale_occupancy

logger = logging.getLogger(__name__)

CHABANAS = 'chabanas'
HAUTEFORT = 'hautefort'
# the nickname of the administrator watching a game, never shown as a participant
ADMIN_NICKNAME = 'Administrateur'


def _date(value: datetime | None) -> str | None:
    return value.isoformat(timespec='seconds') if value is not None else None


def _game_label(game: Game) -> str:
    return game.display_name or game.name


def _variant_labels(game: Game) -> dict:
    """The readable name of each variant of the game, by name."""
    labels = {variant.name: variant.display_name or variant.name for variant in Variant.objects.filter(game=game)}
    labels.setdefault('default', '')
    return labels


def _body(request) -> dict | HttpResponse:
    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        data = None
    if not isinstance(data, dict) or data.get('service') not in (CHABANAS, HAUTEFORT) or not data.get('id'):
        return HttpResponse(BAD_REQUEST, status=400)
    return data


def _unavailable(error: ServiceUnavailable) -> JsonResponse:
    return JsonResponse({'error': str(error)}, status=502)


# -------------------------------------------------
# Reading
# -------------------------------------------------

def chabanas_rows(game: Game, presence: dict | None) -> list:
    """
    The sessions of a game of Chabanas, the active ones first.
    :param presence: who is connected, by session key (Tourtoirac); None: unknown
    """
    variants = _variant_labels(game)
    rows = []
    for session in Session.objects.filter(game=game).order_by('-active', '-created_at'):
        live = (presence or {}).get(str(session.key)) or {}
        online = set(live.get('players', [])) | set(live.get('watchers', []))
        seats = [player.nickname for player in session.player_set.order_by('id')]
        rows.append({
            'service': CHABANAS,
            'id': str(session.key),
            'code': session.code or None,
            'game': _game_label(game),
            'variant': variants.get(session.variant_name, session.variant_name),
            'archived': not session.active,
            'archived_at': _date(session.archived_at),
            'launched_at': _date(session.launched_at),
            'created_at': _date(session.created_at),
            'players': [{'nickname': name, 'connected': name in online} for name in seats],
            'watchers': [name for name in live.get('watchers', []) if name not in seats],
            'occupied': None if presence is None else bool(online),
            'can_access': session.active,
        })
    return rows


def hautefort_rows(module: str, listing: dict) -> list:
    """The games of a module of Hautefort, the unarchived ones first."""
    rows = []
    for game in listing.get('games', []):
        if game['module'] != module:
            continue
        seats = [s for s in game['seats'] if not (s['role'] == 'watcher' and s['nickname'] == ADMIN_NICKNAME)]
        rows.append({
            'service': HAUTEFORT,
            'id': game['id'],
            'code': game['code'],
            'game': game['title'],
            'variant': game.get('variant') or '',
            'archived': game['archived_at'] is not None,
            'archived_at': game['archived_at'],
            'launched_at': game['launched_at'],
            'created_at': game['created_at'],
            'players': [{'nickname': s['nickname'], 'connected': s['connected']}
                        for s in seats if s['role'] == 'player'],
            'watchers': [s['nickname'] for s in seats if s['role'] == 'watcher' and s['connected']],
            'occupied': any(s['connected'] for s in seats),
            'can_access': game['archived_at'] is None,
        })
    # the unarchived first, the newest first within each group
    return sorted(rows, key=lambda row: (row['archived'], -_timestamp(row['created_at'])))


def _timestamp(value: str | None) -> float:
    return datetime.fromisoformat(value).timestamp() if value else 0.0


@staff_member_required
@require_http_methods(["GET"])
def manage_page(request) -> HttpResponse:
    """
    The page of the administration: the drop-down list of the games and the
    table of their sessions, filled by the JSON routes below.
    :param request: Request information
    :type request: Http request
    :return: the page
    :rtype: HttpResponse
    """
    return render(request, 'Session/manage.html')


@staff_member_required
@require_http_methods(["GET"])
def manage_games(request) -> JsonResponse:
    """
    Every game with at least one session, archived or not: the games of
    Chabanas, then the modules of Hautefort.
    :param request: Request information
    :type request: Http request
    :return: {games: [{id, label}], warnings: [...]}
    :rtype: JsonResponse
    """
    games = [
        {'id': f'{CHABANAS}:{game.id}', 'label': _game_label(game)}
        for game in Game.objects.filter(session__isnull=False).distinct()
    ]
    warnings = []
    try:
        listing = manage_clients.hautefort_games()
        played = {game['module'] for game in listing.get('games', [])}
        games += [
            {'id': f"{HAUTEFORT}:{module['module']}", 'label': module['title']}
            for module in listing.get('modules', []) if module['module'] in played
        ]
    except ServiceUnavailable as error:
        warnings.append(f'Les jeux de Hautefort ne sont pas listés : {error}')
    games.sort(key=lambda game: game['label'].lower())
    return JsonResponse({'games': games, 'warnings': warnings})


@staff_member_required
@require_http_methods(["GET"])
def manage_sessions(request) -> HttpResponse:
    """
    The sessions of the game chosen in the list (?game=chabanas:<id> or
    hautefort:<module>).
    :param request: Request information
    :type request: Http request
    :return: {sessions: [...], warnings: [...]}
    :rtype: HttpResponse
    """
    service, _, name = request.GET.get('game', '').partition(':')
    warnings = []
    if service == CHABANAS and name.isdigit():
        game = Game.objects.filter(id=int(name)).first()
        if game is None:
            return HttpResponse(BAD_REQUEST, status=400)
        try:
            presence = manage_clients.tourtoirac_presence()
        except ServiceUnavailable as error:
            presence = None
            warnings.append(f'Les connexions ne sont pas connues : {error}')
        return JsonResponse({'sessions': chabanas_rows(game, presence), 'warnings': warnings})
    if service == HAUTEFORT and name:
        try:
            listing = manage_clients.hautefort_games()
        except ServiceUnavailable as error:
            return _unavailable(error)
        return JsonResponse({'sessions': hautefort_rows(name, listing), 'warnings': warnings})
    return HttpResponse(BAD_REQUEST, status=400)


# -------------------------------------------------
# Actions
# -------------------------------------------------

def _archive(session: Session) -> None:
    """As /session/archive does: the code freed, the session out of the games in progress."""
    session.active = False
    session.code = ''
    session.archived_at = datetime.now(UTC)
    session.save()
    drop_stale_occupancy()


@staff_member_required
@require_http_methods(["POST"])
def manage_archive(request) -> HttpResponse:
    """
    Archives a session and frees its code. The people connected keep watching
    it, the players as watchers, told that the administrator closed it.
    :param request: Request information, JSON {service, id}
    :type request: Http request
    :return: {archived: bool}, False when it already was
    :rtype: HttpResponse
    """
    data = _body(request)
    if not isinstance(data, dict):
        return data
    try:
        if data['service'] == HAUTEFORT:
            return JsonResponse(manage_clients.hautefort_archive(data['id']))
        session = Session.objects.filter(key=data['id']).first()
        if session is None:
            return HttpResponse(status=404)
        if not session.active:
            return JsonResponse({'archived': False})
        # Tourtoirac stores where the tokens are, then archives it through
        # /session/archive; a session nobody is in is archived here
        if not manage_clients.tourtoirac_close(str(session.key)):
            _archive(session)
        else:
            session.refresh_from_db()
            if session.active:
                _archive(session)
    except ServiceUnavailable as error:
        return _unavailable(error)
    logger.info("Session %s archived by %s", data['id'], request.user)
    return JsonResponse({'archived': True})


@staff_member_required
@require_http_methods(["POST"])
def manage_delete(request) -> HttpResponse:
    """
    Deletes a session with its players: the people connected are told and
    taken out of it first.
    :param request: Request information, JSON {service, id}
    :type request: Http request
    :return: {deleted: true}
    :rtype: HttpResponse
    """
    data = _body(request)
    if not isinstance(data, dict):
        return data
    try:
        if data['service'] == HAUTEFORT:
            return JsonResponse(manage_clients.hautefort_delete(data['id']))
        session = Session.objects.filter(key=data['id']).first()
        if session is None:
            return HttpResponse(status=404)
        manage_clients.tourtoirac_delete(str(session.key))
    except ServiceUnavailable as error:
        return _unavailable(error)
    session.delete()
    drop_stale_occupancy()
    logger.info("Session %s deleted by %s", data['id'], request.user)
    return JsonResponse({'deleted': True})


@staff_member_required
@require_http_methods(["POST"])
def manage_access(request) -> HttpResponse:
    """
    The address of the game page that watches a session as the administrator,
    even when it refuses watchers. What the page needs travels in the fragment
    (#admin=...), which the browser never sends to a server.
    :param request: Request information, JSON {service, id}
    :type request: Http request
    :return: {url}
    :rtype: HttpResponse
    """
    data = _body(request)
    if not isinstance(data, dict):
        return data
    site = settings.OBG_SITE_URL
    if data['service'] == HAUTEFORT:
        try:
            seat = manage_clients.hautefort_watch(data['id'])
        except ServiceUnavailable as error:
            return _unavailable(error)
        module, game_id = seat.pop('module'), seat.pop('game_id')
        url = f"{site}hautefort/{module}/?game={quote(game_id)}#admin={quote(json.dumps(seat))}"
        return JsonResponse({'url': url})
    session = Session.objects.filter(key=data['id'], active=True).first()
    if session is None:
        return HttpResponse(status=404)
    entry = {'key': str(session.key), 'code': session.code}
    url = f"{site}game.html?game={quote(session.game.name)}#admin={quote(json.dumps(entry))}"
    return JsonResponse({'url': url})


# -------------------------------------------------
# Refereed games
# -------------------------------------------------

@staff_member_required
@require_http_methods(["GET"])
def manage_refereed_page(request) -> HttpResponse:
    """
    The page of the refereed games, filled by manage_modules.
    :param request: Request information
    :type request: Http request
    :return: the page
    :rtype: HttpResponse
    """
    return render(request, 'Session/manage_refereed.html')


@staff_member_required
@require_http_methods(["GET"])
def manage_modules(request) -> JsonResponse:
    """
    Every refereed game: the modules of Hautefort, whether each one is offered
    in the lobby, and how many games its lobby lists.
    :param request: Request information
    :type request: Http request
    :return: {modules: [{module, title, active, games}]}
    :rtype: JsonResponse
    """
    try:
        return JsonResponse({'modules': manage_clients.hautefort_modules()})
    except ServiceUnavailable as error:
        return _unavailable(error)


@staff_member_required
@require_http_methods(["POST"])
def manage_module_active(request) -> HttpResponse:
    """
    Turns a refereed game on or off.
    :param request: Request information, JSON {module, active}
    :type request: Http request
    :return: {module, active}
    :rtype: HttpResponse
    """
    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get('module'), str) or not data['module'] \
            or not isinstance(data.get('active'), bool):
        return HttpResponse(BAD_REQUEST, status=400)
    try:
        result = manage_clients.hautefort_set_module(data['module'], data['active'])
    except ServiceUnavailable as error:
        return _unavailable(error)
    logger.info("Refereed game %s turned %s by %s", data['module'], 'on' if data['active'] else 'off', request.user)
    return JsonResponse(result)
