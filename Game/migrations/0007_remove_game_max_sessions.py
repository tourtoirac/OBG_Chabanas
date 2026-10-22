from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("Game", "0006_display_name"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="game",
            name="max_sessions",
        ),
    ]
