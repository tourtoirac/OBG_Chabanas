from Game.models import Game


def read_nationalities(game_json) -> list:
    """
    Reads the optional "nationalities" key of the options of a game_json: the
    sides the players of the game choose from when they take a seat.
    :param game_json: the game_json of a game, a variant or a session
    :type game_json: dict
    :return: the nationalities, in the order of the game_json and without
        duplicates; empty when the game declares none
    :rtype: list
    """
    options = game_json.get('options') if isinstance(game_json, dict) else None
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
        "max_sessions": game.max_sessions,
        "variant": {
            "default": {
                "key": game.key,
                "name": "default",
                "min_players": game.min_players,
                "max_players": game.max_players,
                "max_watchers": game.max_watchers,
                "nationalities": read_nationalities(game.game_json),
            }
        }
    }
    variants = [variant for variant in game.variant_set.all() if variant.active]
    for variant in variants:
        game_data['variant'][variant.name] = {
            "key": variant.key,
            "name": variant.name,
            "active": variant.active,
            "min_players": variant.min_players,
            "max_players": variant.max_players,
            "max_watchers": variant.max_watchers,
            # a variant replaces the game_json of the game: its nationalities too
            "nationalities": read_nationalities(variant.game_json),
        }

    return game_data
