from django.db import migrations, models
from django.db.models import F


def date_existing_archives(apps, schema_editor):
    # the sessions archived before this migration were last saved when archived
    Session = apps.get_model("Session", "Session")
    Session.objects.filter(active=False).update(archived_at=F("updated_at"))


class Migration(migrations.Migration):

    dependencies = [
        ('Session', '0003_player_nationality'),
    ]

    operations = [
        migrations.AddField(
            model_name='session',
            name='launched_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='session',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(date_existing_archives, migrations.RunPython.noop),
    ]
