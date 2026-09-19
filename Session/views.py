import logging

from datetime import datetime, timedelta, UTC
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from Chabanas.params_ext import PARAMS_EXT, UNAUTHORIZED
from Chabanas.tools import validate_request
from Game.models import Game, Variant
from Session.tools import (
    generate_session_code,
    return_session_json,
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
        "key",
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
        access_key=key,
        variant_name=variant_name,
        max_players=session_max_players,
        max_watchers=session_max_watchers,
        allows_watchers=allows_watchers,
    )
    Player.objects.create(
        session=session,
        nickname=nickname,
        key=key,
        owner=True,
    )
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
    Returns the list of active sessions filtered by game name
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    requested_values = [
        "game_name_list",
    ]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data

    game_name_list = data['game_name_list']
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
    Allows a user to join an active session
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    requested_values = [
        "session_code",
        "nickname",
        "key",
    ]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data

    nickname = data['nickname']
    key = data['key']
    access_key = data.get('access_key', '')

    session = get_object_or_404(Session, code=data['session_code'])

    if access_key != session.access_key:
        return HttpResponse(status = 401, content=UNAUTHORIZED)

    players_dict = {}
    session_players = Player.objects.filter(session=session)
    for session_player in session_players:
        players_dict[session_player.nickname] = session_player.key

    if nickname in players_dict and players_dict[nickname] == key:
        return JsonResponse(status = 200, data=return_session_json(session, sat_list=['game_json']))

    if nickname in players_dict:
        return HttpResponse(status = 401, content=UNAUTHORIZED)

    if len(players_dict) >= session.max_players:
        return HttpResponse(status = 409, content="Game is full")

    Player.objects.create(
        session=session,
        nickname=nickname,
        key=key,
        owner=False,
    )
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
        "game_json"
    ]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data

    session_key = data['key']
    game_json = data['game_json']

    session = get_object_or_404(Session, key=session_key, active=True)
    session.game_json = game_json
    session.save()

    return HttpResponse("Success", status = 200)
