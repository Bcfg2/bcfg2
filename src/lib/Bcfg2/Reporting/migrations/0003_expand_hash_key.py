# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Reporting', '0002_convert_perms_to_mode'),
    ]

    operations = [
        migrations.AlterField(
            model_name='actionentry',
            name='hash_key',
            field=models.BigIntegerField(editable=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='failureentry',
            name='hash_key',
            field=models.BigIntegerField(editable=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='packageentry',
            name='hash_key',
            field=models.BigIntegerField(editable=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='pathentry',
            name='hash_key',
            field=models.BigIntegerField(editable=False, db_index=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='serviceentry',
            name='hash_key',
            field=models.BigIntegerField(editable=False, db_index=True),
            preserve_default=True,
        ),
    ]
