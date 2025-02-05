# Generated by Django 5.1.5 on 2025-02-05 13:13

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Gear',
            fields=[
                ('id', models.CharField(editable=False, max_length=36, primary_key=True, serialize=False)),
                ('primary', models.BooleanField(default=False, verbose_name='primary')),
                ('brand_name', models.CharField(max_length=30, verbose_name='brand name')),
                ('model_name', models.CharField(max_length=50, verbose_name='brand name')),
                ('description', models.CharField(max_length=100, verbose_name='description')),
                ('json', models.JSONField()),
            ],
        ),
        migrations.CreateModel(
            name='Activity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='name')),
                ('start_date', models.DateTimeField(verbose_name='start date')),
                ('json', models.JSONField()),
                ('gear', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, to='strava.gear')),
            ],
        ),
    ]
