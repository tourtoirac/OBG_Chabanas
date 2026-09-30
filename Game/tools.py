from Game.models import Game


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
        }

    return game_data
