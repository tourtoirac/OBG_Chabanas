from django.db.models import Q, QuerySet

from Game.models import Game, Variant


def listed_games() -> QuerySet:
    """
    The games the lobby lists: an active game, or a game with at least one
    active variant (only its active variants can then be created).
    """
    return Game.objects.filter(Q(active=True) | Q(variant__active=True)).distinct()


def starting_game_json(source) -> dict:
    """
    Builds the game_json a session starts with: the game_json of the game or of
    the variant, where the "options" block is replaced by its options field.
    An "options" key left in the game_json itself is never used.
    :param source: the game or the variant the session is created from
    :type source: Game | Variant
    :return: a new dict, the game_json of the source is left untouched
    :rtype: dict
    """
    game_json = dict(source.game_json) if isinstance(source.game_json, dict) else {}
    game_json['options'] = dict(source.options) if isinstance(source.options, dict) else {}
    return game_json


def read_nationalities(game_json) -> list:
    """
    Reads the optional "nationalities" key of the options of a game_json: the
    sides the players of the game choose from when they take a seat.
    :param game_json: the game_json of a session
    :type game_json: dict
    :return: the nationalities, in the order of the game_json and without
        duplicates; empty when the game declares none
    :rtype: list
    """
    options = game_json.get('options') if isinstance(game_json, dict) else None
    return options_nationalities(options)


def options_nationalities(options) -> list:
    """
    Same as read_nationalities, from the options themselves: the options field
    of a game or of a variant.
    :param options: the options of a game, a variant or a session
    :type options: dict
    :return: the nationalities, in the order of the options and without
        duplicates; empty when the game declares none
    :rtype: list
    """
    declared = options.get('nationalities') if isinstance(options, dict) else None
    if not isinstance(declared, list):
        return []
    nationalities = []
    for nationality in declared:
        if isinstance(nationality, str) and nationality and nationality not in nationalities:
            nationalities.append(nationality)
    return nationalities


def return_game_json(game: Game):
    game_data = {
        "key": game.key,
        "name": game.name,
        # what the lobby shows; the name stays the identifier of the game
        "display_name": game.display_name or game.name,
        # the label of the game tab of the lobby
        "thumbnail_display": game.thumbnail_display or game.display_name or game.name,
        # "Boardgame" or "Wargame": the tab of the lobby the game is listed under
        "type": game.game_type,
        "variant": {}
    }
    # the default variant is the game itself: offered only when the game is active
    if game.active:
        game_data['variant']['default'] = {
            "key": game.key,
            "name": "default",
            "display_name": game.display_name or game.name,
            "min_players": game.min_players,
            "max_players": game.max_players,
            "max_watchers": game.max_watchers,
            "nationalities": options_nationalities(game.options),
        }
    variants = [variant for variant in game.variant_set.all() if variant.active]
    for variant in variants:
        game_data['variant'][variant.name] = {
            "key": variant.key,
            "name": variant.name,
            "display_name": variant.display_name or variant.name,
            "active": variant.active,
            "min_players": variant.min_players,
            "max_players": variant.max_players,
            "max_watchers": variant.max_watchers,
            # a variant replaces the options of the game: its nationalities too
            "nationalities": options_nationalities(variant.options),
        }

    return game_data


def return_definition_json(source) -> dict:
    """Serialize a raw catalogue definition without session option injection."""
    is_variant = isinstance(source, Variant)
    return {
        "key": str(source.key),
        "game_name": source.game.name if is_variant else source.name,
        "variant_name": source.name if is_variant else "default",
        "game_json": source.game_json,
        "updated_at": source.updated_at.isoformat(),
    }
