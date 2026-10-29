from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Game", "0010_nationality_list"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="prototype_key",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
