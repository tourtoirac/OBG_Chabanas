from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Game", "0004_fix_positions_boolean"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="game_type",
            field=models.CharField(
                choices=[("Boardgame", "Boardgame"), ("Wargame", "Wargame")],
                default="Wargame",
                max_length=16,
            ),
        ),
    ]
