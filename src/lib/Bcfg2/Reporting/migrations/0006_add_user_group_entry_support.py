# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Reporting', '0005_add_selinux_entry_support'),
    ]

    operations = [
        migrations.CreateModel(
            name='POSIXGroupEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
                ('gid', models.IntegerField(null=True)),
                ('current_gid', models.IntegerField(null=True)),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='POSIXUserEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
                ('uid', models.IntegerField(null=True)),
                ('current_uid', models.IntegerField(null=True)),
                ('group', models.CharField(max_length=64)),
                ('current_group', models.CharField(max_length=64, null=True)),
                ('gecos', models.CharField(max_length=1024)),
                ('current_gecos', models.CharField(max_length=1024, null=True)),
                ('home', models.CharField(max_length=1024)),
                ('current_home', models.CharField(max_length=1024, null=True)),
                ('shell', models.CharField(default=b'/bin/bash', max_length=1024)),
                ('current_shell', models.CharField(max_length=1024, null=True)),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='interaction',
            name='posixgroups',
            field=models.ManyToManyField(to='Reporting.POSIXGroupEntry'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='interaction',
            name='posixusers',
            field=models.ManyToManyField(to='Reporting.POSIXUserEntry'),
            preserve_default=True,
        ),
    ]
