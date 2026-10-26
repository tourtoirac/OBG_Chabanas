import secrets
import string

from datetime import datetime, timedelta, UTC
from django.db import connection, transaction
from django.db.models import Q

from Chabanas.params_ext import PARAMS_EXT

from Game.tools import read_nationalities
from Session.models import OccupiedGame, ReservedCode, Session, Player

# key of the PostgreSQL advisory lock serialising the admissions of games
OCCUPANCY_LOCK = 0x0B60CC


def active_game_count() -> int:
    """
    Games in progress on the whole platform: the games with at least one player
    in them, every game and service included (OccupiedGame).
    """
    return OccupiedGame.objects.count()


def platform_is_full() -> bool:
    return active_game_count() >= PARAMS_EXT["MAX_ACTIVE_SESSIONS"]


def code_in_use(code: str) -> bool:
    """Whether the code designates a game: an active session, or a reserved code."""
    return (
        Session.objects.filter(code=code, active=True).exists()
        or ReservedCode.objects.filter(code=code).exists()
    )


def occupy_game(code: str, service: str) -> bool:
    """
    A player enters the game of that code. A game already occupied stays so; an
    empty one becomes occupied unless the platform already runs its maximum
    number of games.
    :return: False when the platform is full
    """
    with transaction.atomic():
        # two admissions at once could both see a free place: one at a time
        with connection.cursor() as cursor:
            cursor.execute("select pg_advisory_xact_lock(%s)", [OCCUPANCY_LOCK])
        if OccupiedGame.objects.filter(code=code).exists():
            return True
        if platform_is_full():
            return False
        OccupiedGame.objects.create(code=code, service=service)
        return True


def sync_occupancy(service: str, codes: list) -> tuple[list, list]:
    """
    Checks the occupied games of a service against the list it holds, and
    corrects the database when they differ. The count is kept in real time by
    occupy/vacate; a service sends this list at its start (empty) and every
    hour, so that a missed vacate or a crash never leaves the count wrong for
    long. No limit applies: the list is what the players are doing.
    :return: (codes added, codes removed), both empty when the database was right
    """
    wanted = {code for code in codes if isinstance(code, str) and code and code_in_use(code)}
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("select pg_advisory_xact_lock(%s)", [OCCUPANCY_LOCK])
        stale = OccupiedGame.objects.filter(service=service).exclude(code__in=wanted)
        removed = sorted(stale.values_list('code', flat=True))
        stale.delete()
        known = set(OccupiedGame.objects.filter(code__in=wanted).values_list('code', flat=True))
        added = sorted(wanted - known)
        OccupiedGame.objects.bulk_create([OccupiedGame(code=code, service=service) for code in added])
    return added, removed


def drop_stale_occupancy() -> int:
    """Forgets the occupied games whose code no longer designates a game."""
    active_codes = Session.objects.filter(active=True).values('code')
    reserved_codes = ReservedCode.objects.values('code')
    return OccupiedGame.objects.exclude(code__in=active_codes).exclude(code__in=reserved_codes).delete()[0]


def generate_session_code():
    """
    Generate an 8-character alphanumeric code not already used by an active
    session nor reserved by another service (ReservedCode): Chabanas gives every
    code of the platform, Hautefort included
    """
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(secrets.choice(alphabet) for _ in range(8))
        exists = Session.objects.filter(
            code=code
        ).exclude(
            active=False
        ).exists()

        if not exists and not ReservedCode.objects.filter(code=code).exists():
            return code


def cleanup_sessions():
    """
    Archives the active sessions nobody has launched for SESSION_IDLE_DURATION
    days, which frees their code, then deletes the sessions archived for more
    than SESSION_ARCHIVE_DURATION days, with their players.
    A session never launched counts from its creation.
    :return: (number of sessions archived, number of sessions deleted)
    """
    now = datetime.now(UTC)
    idle_limit = now - timedelta(days=PARAMS_EXT["SESSION_IDLE_DURATION"])
    archived = Session.objects.filter(active=True).filter(
        Q(launched_at__lte=idle_limit)
        | Q(launched_at__isnull=True, created_at__lte=idle_limit)
    ).update(active=False, code='', archived_at=now)

    drop_stale_occupancy()

    archive_limit = now - timedelta(days=PARAMS_EXT["SESSION_ARCHIVE_DURATION"])
    deleted = Session.objects.filter(active=False, archived_at__lte=archive_limit).delete()[1].get(
        Session._meta.label, 0
    )
    return archived, deleted


def session_display_name(session: Session) -> str:
    """
    The readable name of what a session plays: the display_name of its
    variant, or of the game for the default one. A variant since deleted
    falls back on the game.
    """
    game = session.game
    if session.variant_name and session.variant_name != 'default':
        # all() rather than filter(): it reads the variants a prefetch loaded
        for variant in game.variant_set.all():
            if variant.name == session.variant_name:
                return variant.display_name or variant.name
    return game.display_name or game.name


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
        # in the order the players joined the session
        for player in session.player_set.order_by('id')
    ]

    data = {
        "name": session.game.name,
        # what the lobby shows of the game played: its variant, or the game itself
        "display_name": session_display_name(session),
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
        "nationalities": read_nationalities(session.game_json),
    }
    if 'game_json' in sat_list:
        game_json = session.game_json
        game_json['game'] = {
            "max_players": session.max_players,
            "max_watchers": session.max_watchers,
        }
        data['game_json'] = session.game_json
    return data


def seat_nationality(game_json, nationality):
    """
    The nationality to store on a new seat of a game.
    :param game_json: the game_json of the session being created or joined
    :type game_json: dict
    :param nationality: what the player asked for
    :return: the nationality to store, '' when the game declares none; None when
        the game declares some and the player chose none of them
    :rtype: str | None
    """
    nationalities = read_nationalities(game_json)
    if not nationalities:
        return ''
    if nationality in nationalities:
        return nationality
    return None


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
        "nationality": player.nationality or None,
    }
    if 'key' in sat_list:
        player_data['key'] = player.key
    return player_data
