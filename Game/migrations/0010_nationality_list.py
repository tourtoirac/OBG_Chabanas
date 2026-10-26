from django.db import migrations


def convert(value, to_list: bool) -> bool:
    """
    Rewrites in place the nationality of every component of a game_json, at
    any depth (tokens of a bag, cards of a deck, models of a generator...).
    to_list: "US" becomes ["US"]; otherwise a list of one becomes "US" again.
    :return: whether something changed
    """
    changed = False
    if isinstance(value, list):
        for item in value:
            changed = convert(item, to_list) or changed
    elif isinstance(value, dict):
        nationality = value.get("nationality")
        if to_list and isinstance(nationality, str) and nationality:
            value["nationality"] = [nationality]
            changed = True
        elif not to_list and isinstance(nationality, list) and len(nationality) == 1:
            value["nationality"] = nationality[0]
            changed = True
        for item in value.values():
            changed = convert(item, to_list) or changed
    return changed


def rewrite(apps, schema_editor, to_list: bool):
    alias = schema_editor.connection.alias
    for name in ("Game", "Variant"):
        model = apps.get_model("Game", name)
        for row in model.objects.using(alias).all().iterator():
            if convert(row.game_json, to_list):
                row.save(update_fields=["game_json"])


def to_lists(apps, schema_editor):
    rewrite(apps, schema_editor, True)


def to_strings(apps, schema_editor):
    rewrite(apps, schema_editor, False)


class Migration(migrations.Migration):

    dependencies = [
        ("Game", "0009_thumbnail_display"),
    ]

    operations = [
        migrations.RunPython(to_lists, to_strings),
    ]
