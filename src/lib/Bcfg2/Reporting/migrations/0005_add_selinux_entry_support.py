# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('Reporting', '0004_profile_can_be_null'),
    ]

    operations = [
        migrations.CreateModel(
            name='SEBooleanEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
                ('value', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SEFcontextEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
                ('selinuxtype', models.CharField(max_length=128)),
                ('current_selinuxtype', models.CharField(max_length=128, null=True)),
                ('filetype', models.CharField(max_length=16)),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SEInterfaceEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
                ('selinuxtype', models.CharField(max_length=128)),
                ('current_selinuxtype', models.CharField(max_length=128, null=True)),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SELoginEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
                ('selinuxuser', models.CharField(max_length=128)),
                ('current_selinuxuser', models.CharField(max_length=128, null=True)),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SEModuleEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
                ('disabled', models.BooleanField(default=False)),
                ('current_disabled', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SENodeEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
                ('selinuxtype', models.CharField(max_length=128)),
                ('current_selinuxtype', models.CharField(max_length=128, null=True)),
                ('proto', models.CharField(max_length=4)),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SEPermissiveEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SEPortEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
                ('selinuxtype', models.CharField(max_length=128)),
                ('current_selinuxtype', models.CharField(max_length=128, null=True)),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SEUserEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
                ('roles', models.CharField(max_length=128)),
                ('current_roles', models.CharField(max_length=128, null=True)),
                ('prefix', models.CharField(max_length=128)),
                ('current_prefix', models.CharField(max_length=128, null=True)),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='interaction',
            name='sebooleans',
            field=models.ManyToManyField(to='Reporting.SEBooleanEntry'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='interaction',
            name='sefcontexts',
            field=models.ManyToManyField(to='Reporting.SEFcontextEntry'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='interaction',
            name='seinterfaces',
            field=models.ManyToManyField(to='Reporting.SEInterfaceEntry'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='interaction',
            name='selogins',
            field=models.ManyToManyField(to='Reporting.SELoginEntry'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='interaction',
            name='semodules',
            field=models.ManyToManyField(to='Reporting.SEModuleEntry'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='interaction',
            name='senodes',
            field=models.ManyToManyField(to='Reporting.SENodeEntry'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='interaction',
            name='sepermissives',
            field=models.ManyToManyField(to='Reporting.SEPermissiveEntry'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='interaction',
            name='seports',
            field=models.ManyToManyField(to='Reporting.SEPortEntry'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='interaction',
            name='seusers',
            field=models.ManyToManyField(to='Reporting.SEUserEntry'),
            preserve_default=True,
        ),
    ]
