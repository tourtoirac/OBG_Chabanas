import secrets
import string

from Session.models import Session, Player

def generate_session_code():
    """
    Generate an 8-character alphanumeric code not already used in the active sessions
    """
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(8))
        exists = Session.objects.filter(
            code=code
        ).exclude(
            active=False
        ).exists()

        if not exists:
            return code


def return_session_json(session: Session, sat_list=None):
    """
    returns a JSON object with the session data
    :return: 
    """
    if sat_list is None:
        sat_list=['game_json']
    player_list = []
    players = Player.objects.filter(session=session)
    for player in players:
        player_list.append(return_player_json(player, include_key=False))

    data = {
        "name": session.game.name,
        "key": session.key,
        "code": session.code,
        "players" : player_list,
        "active": session.active,
        "variant": session.variant_name,
    }
    if 'game_json' in sat_list:
        data['game_json'] = session.game_json
    return data


def is_session_participant(session: Session, nickname: str, key: str) -> bool:
    return Player.objects.filter(session=session, nickname=nickname, key=key).exists()

def return_player_json(player: Player, include_key=False):
    player_data = {
        "nickname": player.nickname,
        "owner": player.owner,
    }
    if include_key:
        player_data['key'] = player.key
    return player_data
