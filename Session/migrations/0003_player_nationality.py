from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Session', '0002_remove_session_locked_session_started'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='nationality',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
    ]
