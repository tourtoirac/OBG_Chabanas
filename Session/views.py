import logging

from datetime import datetime, timedelta, UTC
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from Chabanas.params_ext import BAD_REQUEST, FORBIDDEN, PARAMS_EXT, UNAUTHORIZED
from Chabanas.tools import validate_request
from Game.models import Game, Variant
from Session.tools import (
    generate_session_code,
    return_session_json,
    start_session_if_full,
)
from Session.models import Session, Player

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def session_create(request) -> HttpResponse:
    """
    Create a Game session if enough space is remaining
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    requested_values = [
        "game_name",
        "nickname",
    ]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data

    logger.debug(f"Creating session with data {data}")

    game_name = data['game_name']
    nickname = data['nickname']
    key = data.get('key', "")
    variant_name = data.get('variant_name', 'default')
    allows_watchers = data.get('allows_watchers', True)
    access_key = data.get('access_key', '')

    game = get_object_or_404(Game, name=game_name)
    variant = None
    if variant_name != 'default':
        variant = get_object_or_404(Variant, game=game, name=variant_name)

    number_of_active_session = Session.objects.filter(game=game, active=True).count()
    logger.debug(f"Number of active sessions for game {game_name}: {number_of_active_session}")
    if number_of_active_session >= game.max_sessions:
        return HttpResponse(status=409, content="Maximum number of active sessions reached")
    game_code = generate_session_code()

    if variant:
        game_json = variant.game_json
        variant_name = variant.name
        default_max_players = variant.max_players
        default_max_watchers = variant.max_watchers
    else:
        game_json = game.game_json
        variant_name = 'default'
        default_max_players = game.max_players
        default_max_watchers = game.max_watchers

    session_max_players = data.get('session_max_players')
    if session_max_players is None:
        session_max_players = default_max_players

    session_max_watchers = data.get('session_max_watchers')
    if session_max_watchers is None:
        session_max_watchers = default_max_watchers

    session = Session.objects.create(
        game = game,
        code=game_code,
        game_json=game_json,
        active=True,
        access_key=access_key,
        variant_name=variant_name,
        max_players=session_max_players,
        max_watchers=session_max_watchers,
        allows_watchers=allows_watchers,
        started=False,
    )
    Player.objects.create(
        session=session,
        nickname=nickname,
        key=key,
        owner=True,
    )
    # a one-seat game is full as soon as it is created
    start_session_if_full(session)
    data = {
        'session_key': session.key,
        'session_code': session.code,
    }
    return JsonResponse(status=201, data=data)

@csrf_exempt
@require_http_methods(["POST"])
def session_get(request) -> HttpResponse:
    """
    Return a session information. Session must be active.
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    requested_values = [
        "session_code",
    ]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data

    session_code = data['session_code']
    sat_list = data.get('sat_list', None)
    session = get_object_or_404(Session, code=session_code, active=True)
    data = {
        'session': return_session_json(session, sat_list=sat_list)
    }
    return JsonResponse(status=200, data=data)

@csrf_exempt
@require_http_methods(["POST"])
def session_list(request) -> HttpResponse:
    """
    Returns the list of active sessions, grouped by active game.
    game_name_list is optional: when given, only these games are listed;
    otherwise every active game of the catalogue is.
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    data = validate_request(request, [])
    if not isinstance(data, dict):
        return data

    game_name_list = data.get('game_name_list')
    if game_name_list is not None and not isinstance(game_name_list, list):
        return HttpResponse(BAD_REQUEST, status=400)
    sat_list = data.get('sat_list', None)

    # deactivates the games that are older than the limit set
    Session.objects.filter(
        active=True,
        created_at__lte=datetime.now(UTC) - timedelta(
            days=PARAMS_EXT["GAME_MAX_DURATION"]
        )
    ).update(active=False, code='')

    active_game_names = set(
        Game.objects.filter(active=True).values_list('name', flat=True)
    )
    if game_name_list is None:
        requested_games = sorted(active_game_names)
    else:
        requested_games = [name for name in game_name_list if name in active_game_names]

    sessions = (
        Session.objects.filter(
            game__name__in=requested_games,
            active=True,
        )
        .select_related("game")
        .prefetch_related("player_set")
    )

    active_games = {name: [] for name in requested_games}
    for session in sessions:
        active_games[session.game.name].append(
            return_session_json(session, sat_list=sat_list)
        )

    data = {
        "sessions": active_games
    }
    logger.debug(data)
    return JsonResponse(status=200, data=data)

@csrf_exempt
@require_http_methods(["POST"])
def session_join(request) -> HttpResponse:
    """
    Allows a user to join an active session.

    The user key is optional: without one the player simply gets a new seat,
    with one they get back the seat that already carries that key for that
    nickname. A wrong key for a known nickname is refused.

    A watcher (role="watcher") is only allowed to watch: it gives a nickname, no
    key, and no row is written to session_players. Spectators are therefore not
    persisted here and never consume a player seat. Counting them is the game
    server's job (Raffaillac/Tourtoirac), which holds the live connections.
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    requested_values = [
        "session_code",
        "nickname",
    ]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data

    role = data.get('role', 'player')
    if role not in ('player', 'watcher'):
        return HttpResponse(status=400, content=BAD_REQUEST)

    nickname = data['nickname']
    key = data.get('key', '')
    access_key = data.get('access_key', '')

    session = get_object_or_404(Session, code=data['session_code'], active=True)

    if access_key != session.access_key:
        return HttpResponse(status = 401, content=UNAUTHORIZED)

    if role == 'watcher':
        if not session.allows_watchers:
            return HttpResponse(status=403, content=FORBIDDEN)
        # a started session only closes its player seats: spectators may still
        # come and watch the game being played
        return JsonResponse(status=200, data=return_session_json(session, sat_list=['game_json']))

    players_dict = {}
    session_players = Player.objects.filter(session=session)
    for session_player in session_players:
        # une ancienne ligne peut porter NULL : la clé vide est une clé valide,
        # elle doit se comparer comme telle
        players_dict[session_player.nickname] = session_player.key or ''

    if nickname in players_dict and players_dict[nickname] == key:
        return JsonResponse(status = 200, data=return_session_json(session, sat_list=['game_json']))

    if nickname in players_dict:
        return HttpResponse(status = 401, content=UNAUTHORIZED)

    # a returning player keeps their seat (handled above); a started session
    # takes no new player
    if session.started:
        return HttpResponse(status = 409, content="Started session. No more player can be added")

    if len(players_dict) >= session.max_players:
        return HttpResponse(status = 409, content="Game is full")

    Player.objects.create(
        session=session,
        nickname=nickname,
        key=key,
        owner=False,
    )
    # the last free seat starts the game
    start_session_if_full(session)
    return JsonResponse(status = 200, data=return_session_json(session, sat_list=['game_json']))


@csrf_exempt
@require_http_methods(["POST"])
def session_get_archive(request) -> HttpResponse:
    """
    Returns an inactive session json
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    requested_values = ["key"]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data

    session = get_object_or_404(Session, key=data['key'], active=False)

    return JsonResponse(status = 200, data=return_session_json(session, sat_list=['game_json']))


@csrf_exempt
@require_http_methods(["POST"])
def session_archive(request) -> HttpResponse:
    """
    Sets a session active value to False
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    requested_values = ["key"]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data
    session = get_object_or_404(Session, key=data['key'], active=True)
    session.active = False
    session.code=''
    session.save()
    return HttpResponse("Success", status = 200)

@csrf_exempt
@require_http_methods(["POST"])
def session_update(request) -> HttpResponse:
    """
    Update session values
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    requested_values = [
        "key",
    ]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data

    session_key = data['key']
    game_json = data.get('game_json', None)
    started = data.get('started', None)

    # a session only ever goes from not started to started: there is no way
    # back once players may have taken components in hand
    if started is not None and started is not True:
        return HttpResponse(status=400, content=BAD_REQUEST)

    session = get_object_or_404(Session, key=session_key, active=True)
    if game_json:
        session.game_json = game_json
        session.save(update_fields=['game_json'])
    if started:
        session.started = True
        session.save(update_fields=['started'])

    return JsonResponse({"status": "success"}, status = 200)
