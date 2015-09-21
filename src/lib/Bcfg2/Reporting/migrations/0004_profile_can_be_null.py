# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Reporting', '0003_expand_hash_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='interaction',
            name='profile',
            field=models.ForeignKey(related_name='+', to='Reporting.Group', null=True),
            preserve_default=True,
        ),
    ]
