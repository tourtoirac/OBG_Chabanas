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
        sat_list=[]

    player_sat_list = []
    if 'player_key' in sat_list:
        player_sat_list = ['key']

    player_list = [
        return_player_json(player, sat_list=player_sat_list)
        for player in session.player_set.all()
    ]

    data = {
        "name": session.game.name,
        "key": session.key,
        "code": session.code,
        "players" : player_list,
        "active": session.active,
        "variant": session.variant_name,
        "access_key": session.access_key,
        "allows_watchers": session.allows_watchers,
        "started": session.started,
        "max_players": session.max_players,
        "max_watchers": session.max_watchers,
    }
    if 'game_json' in sat_list:
        game_json = session.game_json
        game_json['game'] = {
            "max_players": session.max_players,
            "max_watchers": session.max_watchers,
        }
        data['game_json'] = session.game_json
    return data


def start_session_if_full(session: Session) -> bool:
    """
    Starts the session once every player seat is taken.
    :return: True when the session is started after the call
    """
    if not session.started and session.player_set.count() >= session.max_players:
        session.started = True
        session.save(update_fields=['started'])
    return session.started


def is_session_participant(session: Session, nickname: str, key: str) -> bool:
    return Player.objects.filter(session=session, nickname=nickname, key=key).exists()

def return_player_json(player: Player, sat_list=None):
    if sat_list is None:
        sat_list=[]

    player_data = {
        "nickname": player.nickname,
        "owner": player.owner,
    }
    if 'key' in sat_list:
        player_data['key'] = player.key
    return player_data
