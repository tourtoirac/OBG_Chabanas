from django.db import migrations


def add_rotation_steps(apps, schema_editor):
    """Backfill top-level rotatable pieces in games and variants only."""
    alias = schema_editor.connection.alias
    for name in ("Game", "Variant"):
        model = apps.get_model("Game", name)
        for row in model.objects.using(alias).all().iterator():
            document = row.game_json
            if not isinstance(document, dict):
                continue
            changed = False
            for section in ("fixed", "movable", "dice"):
                pieces = document.get(section)
                if not isinstance(pieces, list):
                    continue
                for piece in pieces:
                    if (
                        isinstance(piece, dict)
                        and piece.get("kind") in ("token", "card")
                        and piece.get("orientable") is True
                        and "rotation_step" not in piece
                    ):
                        piece["rotation_step"] = 45
                        changed = True
            if changed:
                row.save(using=alias, update_fields=["game_json"])


class Migration(migrations.Migration):
    dependencies = [("Game", "0007_remove_game_max_sessions")]
    # Existing explicit values must survive both migration and rollback.
    operations = [migrations.RunPython(add_rotation_steps, migrations.RunPython.noop)]
