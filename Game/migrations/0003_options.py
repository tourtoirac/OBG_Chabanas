from django.db import migrations, models


def move_options_out_of_game_json(apps, schema_editor):
    """
    The options of a game used to live in game_json["options"]. They move to
    the new options field, which is the only one read from now on: leaving a
    copy in game_json would let the two drift apart.
    """
    for name in ("Game", "Variant"):
        model = apps.get_model("Game", name)
        for row in model.objects.all().iterator():
            if not isinstance(row.game_json, dict) or "options" not in row.game_json:
                continue
            game_json = dict(row.game_json)
            options = game_json.pop("options")
            row.options = options if isinstance(options, dict) else {}
            row.game_json = game_json
            row.save(update_fields=["game_json", "options"])


def move_options_back_into_game_json(apps, schema_editor):
    for name in ("Game", "Variant"):
        model = apps.get_model("Game", name)
        for row in model.objects.all().iterator():
            if not row.options or not isinstance(row.game_json, dict):
                continue
            row.game_json = {**row.game_json, "options": row.options}
            row.save(update_fields=["game_json"])


class Migration(migrations.Migration):

    dependencies = [
        ("Game", "0002_token_orientable_false"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="options",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="variant",
            name="options",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(move_options_out_of_game_json, move_options_back_into_game_json),
    ]
