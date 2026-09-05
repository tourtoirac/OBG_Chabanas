import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from Chabanas.tools import validate_request
from Game.models import Game
from Game.tools import return_game_json

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["POST"])
def game_list(request) -> HttpResponse:
    """
    returns a list of games and their description based on the accepted games value passed
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

    games = Game.objects.filter(name__in=game_name_list)
    game_list = []
    for game in games:
        game_list.append(return_game_json(game))
    data = {
        "game_list": game_list
    }
    return JsonResponse(status=200, data=data)
