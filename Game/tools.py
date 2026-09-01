import secrets
import string

from Game.models import Session

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
    data = {
        "name": session.game.name,
        "code": session.code,
        "player1_nickname": session.player1_nickname,
        "player1_key": session.player1_key,
        "player2_nickname": session.player2_nickname,
        "player2_key": session.player2_key,
        "active": session.active,
    }
    if 'game_json' in sat_list:
        data['game_json'] = session.game_json
    return data


def is_session_participant(session: Session, nickname: str, key: str) -> bool:
    result = (session.player1_nickname == nickname and session.player1_key == key) or (
                session.player2_nickname == nickname or session.player2_key == key)
    return result
