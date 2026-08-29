import secrets
import string

from Waterloo.models import Waterloo

def generate_waterloo_code():
    """
    Generate an 8-character alphanumeric code not already used in the active games
    """
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(8))
        exists = Waterloo.objects.filter(
            waterloo_code=code
        ).exclude(
            active=False
        ).exists()

        if not exists:
            return code


def return_waterloo_json(game: Waterloo, sat_list=None):
    """
    returns a JSON object with the game data
    :return: 
    """
    if sat_list is None:
        sat_list=['game_json']
    data = {
        'key': game.waterloo_key,
        "code": game.waterloo_code,
        "player1_nickname": game.player1_nickname,
        "player1_key": game.player1_key,
        "player2_nickname": game.player2_nickname,
        "player2_key": game.player2_key,
        "active": game.active,
    }
    if 'game_json' in sat_list:
        data['game_json'] = game.game_json
    return data


def is_game_participant(game: Waterloo, nickname: str, key: str) -> bool:
    result = (game.player1_nickname == nickname and game.player1_key == key) or (
                game.player2_nickname == nickname or game.player2_key == key)
    return result
