import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from Chabanas.params_ext import BAD_REQUEST
from Chabanas.tools import validate_request
from Game.models import Game
from Game.tools import listed_games, return_game_json

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def game_list(request) -> HttpResponse:
    """
    returns a list of games and their description.
    game_name_list is optional: when given, only these games are returned
    (active or not); otherwise every game of the catalogue that is active or
    has an active variant is.
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

    if game_name_list is None:
        games = listed_games()
    else:
        games = Game.objects.filter(name__in=game_name_list)
    games = games.order_by("name").prefetch_related("variant_set")
    game_list = []
    for game in games:
        game_list.append(return_game_json(game))
    data = {
        "game_list": game_list
    }
    return JsonResponse(status=200, data=data)
