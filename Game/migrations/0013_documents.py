from django.db import migrations, models


def documents_of(game_json) -> list:
    """The "documents" block of a game_json, cleaned as Tourtoirac read it."""
    declared = game_json.get("documents") if isinstance(game_json, dict) else None
    documents = []
    for document in declared if isinstance(declared, list) else []:
        if not isinstance(document, dict):
            continue
        src = document.get("src")
        if not isinstance(src, str) or not src:
            continue
        name = document.get("name")
        documents.append({"src": src, "name": name if isinstance(name, str) and name else src})
    return documents


def move_documents_out(apps, schema_editor):
    """The documents leave the game_json of the games and variants for their own field."""
    for model in (apps.get_model("Game", "Game"), apps.get_model("Game", "Variant")):
        for row in model.objects.all():
            if not isinstance(row.game_json, dict) or "documents" not in row.game_json:
                continue
            row.documents = documents_of(row.game_json)
            row.game_json = {key: value for key, value in row.game_json.items() if key != "documents"}
            row.save(update_fields=["documents", "game_json"])


def move_documents_back(apps, schema_editor):
    for model in (apps.get_model("Game", "Game"), apps.get_model("Game", "Variant")):
        for row in model.objects.all():
            if row.documents and isinstance(row.game_json, dict):
                row.game_json = {**row.game_json, "documents": row.documents}
                row.save(update_fields=["game_json"])


class Migration(migrations.Migration):

    dependencies = [
        ('Game', '0012_prototype_users'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='documents',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='variant',
            name='documents',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(move_documents_out, move_documents_back),
    ]
