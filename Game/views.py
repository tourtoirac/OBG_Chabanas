import logging

from datetime import datetime, timedelta, UTC
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from Chabanas.params_ext import PARAMS_EXT, UNAUTHORIZED
from Chabanas.tools import validate_request
from Game.models import Game, Session
from Game.tools import (
    generate_session_code,
    is_session_participant,
    return_session_json,
)

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
        "name",
        "player_nickname",
        "player_key",
    ]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data

    game_name = data['name']
    nickname = data['player_nickname']
    key = data['player_key']

    game = get_object_or_404(Game, name=game_name)

    number_of_active_session = Session.objects.filter(active=True).count()
    if number_of_active_session > PARAMS_EXT['MAX_ACTIVE_SESSIONS']:
        return HttpResponse(status=409, content="Maximum number of active sessions reached")
    game_code = generate_session_code()
    session = Session.objects.create(
        game = game,
        code=game_code,
        player1_nickname=nickname,
        player1_key=key,
        game_json=game.game_json,
        active=True,
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
    session = get_object_or_404(Session, code=session_code, active=True)

    data = {
        'session': return_session_json(session, sat_list=['game_json'])
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
    data = validate_request(request, [])
    sat_list = data.get('sat_list', None)

    # deactivates the games that are older than the limit set
    Session.objects.filter(
        active=True,
        created_at__lte=datetime.now(UTC) - timedelta(
            days=PARAMS_EXT["GAME_MAX_DURATION"]
        )
    ).update(active=False, code='')

    active_games = []
    game_names = Game.objects.filter(active=True).values_list('name', flat=True)
    for name in game_names:
        active_games[name] = []
        sessions = Session.objects.filter(game__name=name, active=True)
        for session in sessions:
            active_games[name].append(return_session_json(session, sat_list=sat_list))

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
        "code",
        "nickname",
        "key",
    ]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data

    nickname = data['nickname']
    key = data['key']

    session = get_object_or_404(Session, waterloo_code=data['code'])

    if is_session_participant(session, nickname, key):
        return JsonResponse(status = 200, data=return_session_json(session, sat_list=['game_json']))

    if nickname in (session.player1_nickname, session.player2_nickname):
        return HttpResponse(status = 401, content=UNAUTHORIZED)

    if session.player2_nickname == '':
        session.player2_nickname = nickname
        session.player2_key = key
        session.save()
        return JsonResponse(status = 200, data=return_session_json(session, sat_list=['game_json']))

    return HttpResponse(status = 409, content="Game is full")


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
    session = get_object_or_404(Session, key=data['key'])
    session.active = False
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

    session = get_object_or_404(Session, key=session_key)
    if not session.active:
        return HttpResponse(UNAUTHORIZED, status=401)

    session.game_json = game_json
    session.save()

    return HttpResponse("Success", status = 200)
