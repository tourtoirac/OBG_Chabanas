from Game.models import Game, Variant


def return_game_json(game: Game):
    game_data = {
        "key": game.key,
        "name": game.name,
        "max_sessions": game.max_sessions,
        "variant": {
            "default": {
                "key": game.key,
                "name": "default",
                "game_json": game.game_json,
                "max_players": game.max_players,
                "max_watchers": game.max_watchers,

            }
        }
    }
    variant = Variant.objects.filter(game=game, active=True)
    if variant.exists():
        for variant in variant:
            game_data['variant'][variant.name] = {
                "key": variant.key,
                "name": variant.name,
                "game_json": variant.game_json,
                "active": variant.active,
                "max_players": variant.max_players,
                "max_watchers": variant.max_watchers,
            }

    return game_data
