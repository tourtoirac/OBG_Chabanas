import logging

from datetime import datetime, timedelta, UTC
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from Chabanas.params_ext import PARAMS_EXT, UNAUTHORIZED
from Chabanas.tools import validate_request
from Waterloo.models import Waterloo
from Waterloo.tools import (
    generate_waterloo_code,
    is_game_participant,
    return_waterloo_json,
)
from Waterloo.waterloo_settings import GAME_JSON

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def waterloo_create(request) -> HttpResponse:
    """
    Create a Waterloo session if enough space is remaining
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    requested_values = [
        "player_nickname",
        "player_key",
    ]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data

    nickname = data['player_nickname']
    key = data['player_key']

    number_of_active_session = Waterloo.objects.filter(active=True).count()
    if number_of_active_session > PARAMS_EXT['MAX_ACTIVE_SESSIONS']:
        return HttpResponse(status=409, content="Maximum number of active sessions reached")
    game_code = generate_waterloo_code()
    game = Waterloo.objects.create(
        waterloo_code=game_code,
        player1_nickname=nickname,
        player1_key=key,
        game_json=GAME_JSON,
        active=True,
    )
    data = {
        'game_key': game.waterloo_key,
        'game_code': game.waterloo_code,
    }
    return JsonResponse(status=201, data=data)

@csrf_exempt
@require_http_methods(["POST"])
def waterloo_get(request) -> HttpResponse:
    """
    Return a Waterloo game information. Game must be active.
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    requested_values = [
        "game_code",
    ]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data

    game_code = data['game_code']
    game = get_object_or_404(Waterloo, waterloo_code=game_code, active=True)

    data = {
        'game': return_waterloo_json(game, sat_list=['game_json'])
    }
    return JsonResponse(status=200, data=data)

@csrf_exempt
@require_http_methods(["POST"])
def waterloo_list(request) -> HttpResponse:
    """
    Returns the list of active sessions
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    data = validate_request(request, [])
    sat_list = data.get('sat_list', None)

    # deactivates the games that are older than the limit set
    Waterloo.objects.filter(
        active=True,
        created_at__lte=datetime.now(UTC) - timedelta(
            days=PARAMS_EXT["GAME_MAX_DURATION"]
        )
    ).update(active=False, waterloo_code='')

    games = Waterloo.objects.filter(active=True).order_by('-created_at')
    active_games = []
    for game in games:
        active_games.append(return_waterloo_json(game, sat_list=sat_list))

    data = {
        "games": active_games
    }
    logger.debug(data)
    return JsonResponse(status=200, data=data)

@csrf_exempt
@require_http_methods(["POST"])
def waterloo_join(request) -> HttpResponse:
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

    game = get_object_or_404(Waterloo, waterloo_code=data['code'])

    if is_game_participant(game, nickname, key):
        return JsonResponse(status = 200, data=return_waterloo_json(game))

    if nickname in (game.player1_nickname, game.player2_nickname):
        return HttpResponse(status = 401, content=UNAUTHORIZED)

    if game.player2_nickname == '':
        game.player2_nickname = nickname
        game.player2_key = key
        game.save()
        return JsonResponse(status = 200, data=return_waterloo_json(game))

    return HttpResponse(status = 409, content="Game is full")


@csrf_exempt
@require_http_methods(["POST"])
def waterloo_get_archive(request) -> HttpResponse:
    """
    Returns an inactive game json
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    requested_values = ["key"]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data
    game = get_object_or_404(Waterloo, waterloo_key=data['key'], active=False)
    return JsonResponse(status = 200, data=return_waterloo_json(game))


@csrf_exempt
@require_http_methods(["POST"])
def waterloo_archive(request) -> HttpResponse:
    """
    Sets a game active value to False
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    requested_values = ["key"]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data
    game = get_object_or_404(Waterloo, waterloo_key=data['key'])
    game.active = False
    game.save()
    return HttpResponse("Success", status = 200)

@csrf_exempt
@require_http_methods(["POST"])
def waterloo_update(request) -> HttpResponse:
    """
    Update game values
    :param request: Request information
    :type request: Http request
    :return: HTTP response code
    :rtype: HttpResponse
    """
    requested_values = [
        "waterloo_key",
        "game_json"
    ]
    data = validate_request(request, requested_values)
    if not isinstance(data, dict):
        return data

    waterloo_key = data['waterloo_key']
    game_json = data['game_json']

    game = get_object_or_404(Waterloo, waterloo_key=waterloo_key)
    if not game.active:
        return HttpResponse(UNAUTHORIZED, status=401)

    game.game_json = game_json
    game.save()

    return HttpResponse("Success", status = 200)
