from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Game", "0005_game_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="display_name",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="variant",
            name="display_name",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
    ]
