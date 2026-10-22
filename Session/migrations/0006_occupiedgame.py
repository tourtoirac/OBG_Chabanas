from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Session', '0005_reservedcode'),
    ]

    operations = [
        migrations.CreateModel(
            name='OccupiedGame',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=64, unique=True)),
                ('service', models.CharField(max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'occupied_game',
            },
        ),
    ]
