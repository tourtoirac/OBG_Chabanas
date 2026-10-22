from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Session', '0004_session_launched_at_archived_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReservedCode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=64, unique=True)),
                ('owner', models.CharField(max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'reserved_code',
            },
        ),
    ]
