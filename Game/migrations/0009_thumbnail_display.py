from django.db import migrations, models


def copy_display_name(apps, schema_editor):
    """The existing games keep the label their tab already showed."""
    alias = schema_editor.connection.alias
    game = apps.get_model("Game", "Game")
    for row in game.objects.using(alias).all().iterator():
        row.thumbnail_display = row.display_name
        row.save(update_fields=["thumbnail_display"])


class Migration(migrations.Migration):

    dependencies = [
        ("Game", "0008_token_rotation_step"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="thumbnail_display",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.RunPython(copy_display_name, migrations.RunPython.noop),
    ]
