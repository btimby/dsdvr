# Generated by Django 2.1.7 on 2019-02-14 23:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='stream',
            name='resume_seconds',
        ),
        migrations.AddField(
            model_name='stream',
            name='cursor',
            field=models.DecimalField(decimal_places=6, max_digits=12, null=True),
        ),
    ]
