# Generated by Django 2.1.1 on 2019-08-01 16:10

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adventure', '0002_player_moves'),
    ]

    operations = [
        migrations.AlterField(
            model_name='game',
            name='map_columns',
            field=models.PositiveIntegerField(default=5, validators=[django.core.validators.MinValueValidator(2), django.core.validators.MaxValueValidator(10)]),
        ),
    ]
