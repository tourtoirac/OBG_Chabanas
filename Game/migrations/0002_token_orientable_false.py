from django.db import migrations

# Les listes du game_json où peut se trouver un composant. On les parcourt
# toutes plutôt que seulement "movable" : où un jeu range ses pions est son
# affaire, la demande porte sur tous les tokens.
LISTES = ("fixed", "movable", "dice")


def tokens_sans_orientable(game_json):
    """
    :return: les positions (liste, index) des tokens de ce game_json qui n'ont
    pas encore la clé "orientable". Une clé déjà présente n'est pas touchée :
    si un jeu a choisi de rendre un pion orientable, l'écraser lui volerait ce
    choix, donc on ne l'écrase pas.
    """
    positions = []
    for liste in LISTES:
        for index, composant in enumerate(game_json.get(liste) or []):
            if composant.get('kind') == 'token' and 'orientable' not in composant:
                positions.append((liste, index))
    return positions


def pose_orientable_false(apps, schema_editor):
    """Ajoute orientable=False à tous les tokens de Game et de Variant."""
    Game = apps.get_model("Game", "Game")
    Variant = apps.get_model("Game", "Variant")
    for model in (Game, Variant):
        for ligne in model.objects.all().iterator():
            positions = tokens_sans_orientable(ligne.game_json)
            if not positions:
                continue
            game_json = dict(ligne.game_json)
            for liste, index in positions:
                composants = list(game_json[liste])
                composants[index] = {**composants[index], 'orientable': False}
                game_json[liste] = composants
            ligne.game_json = game_json
            ligne.save(update_fields=['game_json'])


class Migration(migrations.Migration):
    """
    Les pions sont posés à plat : orientable=false. Diplomacy portait déjà ce
    drapeau dans son game_json, les autres jeux non ; on l'aligne partout.

    L'annulation ne retire rien. Cette migration corrige une donnée pour la
    mettre en accord avec les fichiers de jeu, il n'y a pas d'"avant" à
    restaurer : supprimer la clé effacerait aussi les valeurs posées à la
    main pour Diplomacy, qui existaient avant cette migration. Ne rien faire
    en arrière ne perd aucune donnée, lui, si.
    """

    dependencies = [
        ("Game", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(pose_orientable_false, migrations.RunPython.noop),
    ]
