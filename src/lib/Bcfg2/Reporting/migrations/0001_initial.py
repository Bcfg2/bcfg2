# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ActionEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
                ('status', models.CharField(default=b'check', max_length=128)),
                ('output', models.IntegerField(default=0)),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Bundle',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=255)),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Client',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('creation', models.DateTimeField(auto_now_add=True)),
                ('name', models.CharField(max_length=128)),
                ('expiration', models.DateTimeField(null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='FailureEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('entry_type', models.CharField(max_length=128)),
                ('message', models.TextField()),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='FileAcl',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='FilePerms',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('owner', models.CharField(max_length=128)),
                ('group', models.CharField(max_length=128)),
                ('mode', models.CharField(max_length=128)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(unique=True, max_length=255)),
                ('profile', models.BooleanField(default=False)),
                ('public', models.BooleanField(default=False)),
                ('category', models.CharField(max_length=1024, blank=True)),
                ('comment', models.TextField(blank=True)),
                ('bundles', models.ManyToManyField(to='Reporting.Bundle')),
                ('groups', models.ManyToManyField(to='Reporting.Group')),
            ],
            options={
                'ordering': ('name',),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Interaction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('timestamp', models.DateTimeField(db_index=True)),
                ('state', models.CharField(max_length=32)),
                ('repo_rev_code', models.CharField(max_length=64)),
                ('server', models.CharField(max_length=256)),
                ('good_count', models.IntegerField()),
                ('total_count', models.IntegerField()),
                ('bad_count', models.IntegerField(default=0)),
                ('modified_count', models.IntegerField(default=0)),
                ('extra_count', models.IntegerField(default=0)),
                ('actions', models.ManyToManyField(to='Reporting.ActionEntry')),
                ('bundles', models.ManyToManyField(to='Reporting.Bundle')),
                ('client', models.ForeignKey(related_name='interactions', to='Reporting.Client')),
                ('failures', models.ManyToManyField(to='Reporting.FailureEntry')),
                ('groups', models.ManyToManyField(to='Reporting.Group')),
            ],
            options={
                'ordering': ['-timestamp'],
                'get_latest_by': 'timestamp',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PackageEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
                ('target_version', models.CharField(default=b'', max_length=1024)),
                ('current_version', models.CharField(max_length=1024)),
                ('verification_details', models.TextField(default=b'')),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='PathEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
                ('path_type', models.CharField(max_length=128, choices=[(b'device', b'Device'), (b'directory', b'Directory'), (b'hardlink', b'Hard Link'), (b'nonexistent', b'Non Existent'), (b'permissions', b'Permissions'), (b'symlink', b'Symlink')])),
                ('detail_type', models.IntegerField(default=0, choices=[(0, b'Unused'), (1, b'Diff'), (2, b'Binary'), (3, b'Sensitive'), (4, b'Size limit exceeded'), (5, b'VCS output'), (6, b'Pruned paths')])),
                ('details', models.TextField(default=b'')),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='LinkEntry',
            fields=[
                ('pathentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='Reporting.PathEntry')),
                ('target_path', models.CharField(max_length=1024, blank=True)),
                ('current_path', models.CharField(max_length=1024, blank=True)),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=('Reporting.pathentry',),
        ),
        migrations.CreateModel(
            name='DeviceEntry',
            fields=[
                ('pathentry_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='Reporting.PathEntry')),
                ('device_type', models.CharField(max_length=16, choices=[(b'block', b'Block'), (b'char', b'Char'), (b'fifo', b'Fifo')])),
                ('target_major', models.IntegerField()),
                ('target_minor', models.IntegerField()),
                ('current_major', models.IntegerField()),
                ('current_minor', models.IntegerField()),
            ],
            options={
                'ordering': ('state', 'name'),
                'abstract': False,
            },
            bases=('Reporting.pathentry',),
        ),
        migrations.CreateModel(
            name='Performance',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('metric', models.CharField(max_length=128)),
                ('value', models.DecimalField(max_digits=32, decimal_places=16)),
                ('interaction', models.ForeignKey(related_name='performance_items', to='Reporting.Interaction')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
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
            name='ServiceEntry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=128, db_index=True)),
                ('hash_key', models.BigIntegerField(editable=False, db_index=True)),
                ('state', models.IntegerField(choices=[(0, b'Good'), (1, b'Bad'), (2, b'Modified'), (3, b'Extra')])),
                ('exists', models.BooleanField(default=True)),
                ('target_status', models.CharField(default=b'', max_length=128)),
                ('current_status', models.CharField(default=b'', max_length=128)),
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
            model_name='pathentry',
            name='acls',
            field=models.ManyToManyField(to='Reporting.FileAcl'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pathentry',
            name='current_perms',
            field=models.ForeignKey(related_name='+', to='Reporting.FilePerms'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pathentry',
            name='target_perms',
            field=models.ForeignKey(related_name='+', to='Reporting.FilePerms'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='interaction',
            name='packages',
            field=models.ManyToManyField(to='Reporting.PackageEntry'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='interaction',
            name='paths',
            field=models.ManyToManyField(to='Reporting.PathEntry'),
            preserve_default=True,
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
        migrations.AddField(
            model_name='interaction',
            name='profile',
            field=models.ForeignKey(related_name='+', to='Reporting.Group', null=True),
            preserve_default=True,
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
            name='services',
            field=models.ManyToManyField(to='Reporting.ServiceEntry'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='interaction',
            name='seusers',
            field=models.ManyToManyField(to='Reporting.SEUserEntry'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='interaction',
            unique_together=set([('client', 'timestamp')]),
        ),
        migrations.AlterUniqueTogether(
            name='fileperms',
            unique_together=set([('owner', 'group', 'mode')]),
        ),
        migrations.AddField(
            model_name='client',
            name='current_interaction',
            field=models.ForeignKey(related_name='parent_client', blank=True, to='Reporting.Interaction', null=True),
            preserve_default=True,
        ),
    ]
