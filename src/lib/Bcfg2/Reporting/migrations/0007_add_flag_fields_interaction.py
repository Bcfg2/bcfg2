# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Reporting', '0006_add_user_group_entry_support'),
    ]

    operations = [
        migrations.AddField(
            model_name='interaction',
            name='dry_run',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='interaction',
            name='only_important',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
