# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'Client'
        db.create_table('Reporting_client', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('creation', self.gf('django.db.models.fields.DateTimeField')(auto_now_add=True, blank=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('current_interaction', self.gf('django.db.models.fields.related.ForeignKey')(blank=True, related_name='parent_client', null=True, to=orm['Reporting.Interaction'])),
            ('expiration', self.gf('django.db.models.fields.DateTimeField')(null=True, blank=True)),
        ))
        db.send_create_signal('Reporting', ['Client'])

        # Adding model 'Interaction'
        db.create_table('Reporting_interaction', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('client', self.gf('django.db.models.fields.related.ForeignKey')(related_name='interactions', to=orm['Reporting.Client'])),
            ('timestamp', self.gf('django.db.models.fields.DateTimeField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.CharField')(max_length=32)),
            ('repo_rev_code', self.gf('django.db.models.fields.CharField')(max_length=64)),
            ('server', self.gf('django.db.models.fields.CharField')(max_length=256)),
            ('good_count', self.gf('django.db.models.fields.IntegerField')()),
            ('total_count', self.gf('django.db.models.fields.IntegerField')()),
            ('bad_count', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('modified_count', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('extra_count', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('profile', self.gf('django.db.models.fields.related.ForeignKey')(related_name='+', to=orm['Reporting.Group'])),
        ))
        db.send_create_signal('Reporting', ['Interaction'])

        # Adding unique constraint on 'Interaction', fields ['client', 'timestamp']
        db.create_unique('Reporting_interaction', ['client_id', 'timestamp'])

        # Adding M2M table for field actions on 'Interaction'
        db.create_table('Reporting_interaction_actions', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('actionentry', models.ForeignKey(orm['Reporting.actionentry'], null=False))
        ))
        db.create_unique('Reporting_interaction_actions', ['interaction_id', 'actionentry_id'])

        # Adding M2M table for field packages on 'Interaction'
        db.create_table('Reporting_interaction_packages', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('packageentry', models.ForeignKey(orm['Reporting.packageentry'], null=False))
        ))
        db.create_unique('Reporting_interaction_packages', ['interaction_id', 'packageentry_id'])

        # Adding M2M table for field paths on 'Interaction'
        db.create_table('Reporting_interaction_paths', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('pathentry', models.ForeignKey(orm['Reporting.pathentry'], null=False))
        ))
        db.create_unique('Reporting_interaction_paths', ['interaction_id', 'pathentry_id'])

        # Adding M2M table for field services on 'Interaction'
        db.create_table('Reporting_interaction_services', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('serviceentry', models.ForeignKey(orm['Reporting.serviceentry'], null=False))
        ))
        db.create_unique('Reporting_interaction_services', ['interaction_id', 'serviceentry_id'])

        # Adding M2M table for field failures on 'Interaction'
        db.create_table('Reporting_interaction_failures', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('failureentry', models.ForeignKey(orm['Reporting.failureentry'], null=False))
        ))
        db.create_unique('Reporting_interaction_failures', ['interaction_id', 'failureentry_id'])

        # Adding M2M table for field groups on 'Interaction'
        db.create_table('Reporting_interaction_groups', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('group', models.ForeignKey(orm['Reporting.group'], null=False))
        ))
        db.create_unique('Reporting_interaction_groups', ['interaction_id', 'group_id'])

        # Adding M2M table for field bundles on 'Interaction'
        db.create_table('Reporting_interaction_bundles', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('bundle', models.ForeignKey(orm['Reporting.bundle'], null=False))
        ))
        db.create_unique('Reporting_interaction_bundles', ['interaction_id', 'bundle_id'])

        # Adding model 'Performance'
        db.create_table('Reporting_performance', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('interaction', self.gf('django.db.models.fields.related.ForeignKey')(related_name='performance_items', to=orm['Reporting.Interaction'])),
            ('metric', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('value', self.gf('django.db.models.fields.DecimalField')(max_digits=32, decimal_places=16)),
        ))
        db.send_create_signal('Reporting', ['Performance'])

        # Adding model 'Group'
        db.create_table('Reporting_group', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
            ('profile', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('public', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('category', self.gf('django.db.models.fields.CharField')(max_length=1024, blank=True)),
            ('comment', self.gf('django.db.models.fields.TextField')(blank=True)),
        ))
        db.send_create_signal('Reporting', ['Group'])

        # Adding M2M table for field groups on 'Group'
        db.create_table('Reporting_group_groups', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('from_group', models.ForeignKey(orm['Reporting.group'], null=False)),
            ('to_group', models.ForeignKey(orm['Reporting.group'], null=False))
        ))
        db.create_unique('Reporting_group_groups', ['from_group_id', 'to_group_id'])

        # Adding M2M table for field bundles on 'Group'
        db.create_table('Reporting_group_bundles', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('group', models.ForeignKey(orm['Reporting.group'], null=False)),
            ('bundle', models.ForeignKey(orm['Reporting.bundle'], null=False))
        ))
        db.create_unique('Reporting_group_bundles', ['group_id', 'bundle_id'])

        # Adding model 'Bundle'
        db.create_table('Reporting_bundle', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
        ))
        db.send_create_signal('Reporting', ['Bundle'])

        # Adding model 'FilePerms'
        db.create_table('Reporting_fileperms', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('owner', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('group', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('perms', self.gf('django.db.models.fields.CharField')(max_length=128)),
        ))
        db.send_create_signal('Reporting', ['FilePerms'])

        # Adding unique constraint on 'FilePerms', fields ['owner', 'group', 'perms']
        db.create_unique('Reporting_fileperms', ['owner', 'group', 'perms'])

        # Adding model 'FileAcl'
        db.create_table('Reporting_fileacl', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
        ))
        db.send_create_signal('Reporting', ['FileAcl'])

        # Adding model 'FailureEntry'
        db.create_table('Reporting_failureentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('hash_key', self.gf('django.db.models.fields.IntegerField')(db_index=True)),
            ('entry_type', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('message', self.gf('django.db.models.fields.TextField')()),
        ))
        db.send_create_signal('Reporting', ['FailureEntry'])

        # Adding model 'ActionEntry'
        db.create_table('Reporting_actionentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('hash_key', self.gf('django.db.models.fields.IntegerField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.IntegerField')()),
            ('exists', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('status', self.gf('django.db.models.fields.CharField')(default='check', max_length=128)),
            ('output', self.gf('django.db.models.fields.IntegerField')(default=0)),
        ))
        db.send_create_signal('Reporting', ['ActionEntry'])

        # Adding model 'PackageEntry'
        db.create_table('Reporting_packageentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('hash_key', self.gf('django.db.models.fields.IntegerField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.IntegerField')()),
            ('exists', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('target_version', self.gf('django.db.models.fields.CharField')(default='', max_length=1024)),
            ('current_version', self.gf('django.db.models.fields.CharField')(max_length=1024)),
            ('verification_details', self.gf('django.db.models.fields.TextField')(default='')),
        ))
        db.send_create_signal('Reporting', ['PackageEntry'])

        # Adding model 'PathEntry'
        db.create_table('Reporting_pathentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('hash_key', self.gf('django.db.models.fields.IntegerField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.IntegerField')()),
            ('exists', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('path_type', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('target_perms', self.gf('django.db.models.fields.related.ForeignKey')(related_name='+', to=orm['Reporting.FilePerms'])),
            ('current_perms', self.gf('django.db.models.fields.related.ForeignKey')(related_name='+', to=orm['Reporting.FilePerms'])),
            ('detail_type', self.gf('django.db.models.fields.IntegerField')(default=0)),
            ('details', self.gf('django.db.models.fields.TextField')(default='')),
        ))
        db.send_create_signal('Reporting', ['PathEntry'])

        # Adding M2M table for field acls on 'PathEntry'
        db.create_table('Reporting_pathentry_acls', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('pathentry', models.ForeignKey(orm['Reporting.pathentry'], null=False)),
            ('fileacl', models.ForeignKey(orm['Reporting.fileacl'], null=False))
        ))
        db.create_unique('Reporting_pathentry_acls', ['pathentry_id', 'fileacl_id'])

        # Adding model 'LinkEntry'
        db.create_table('Reporting_linkentry', (
            ('pathentry_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['Reporting.PathEntry'], unique=True, primary_key=True)),
            ('target_path', self.gf('django.db.models.fields.CharField')(max_length=1024, blank=True)),
            ('current_path', self.gf('django.db.models.fields.CharField')(max_length=1024, blank=True)),
        ))
        db.send_create_signal('Reporting', ['LinkEntry'])

        # Adding model 'DeviceEntry'
        db.create_table('Reporting_deviceentry', (
            ('pathentry_ptr', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['Reporting.PathEntry'], unique=True, primary_key=True)),
            ('device_type', self.gf('django.db.models.fields.CharField')(max_length=16)),
            ('target_major', self.gf('django.db.models.fields.IntegerField')()),
            ('target_minor', self.gf('django.db.models.fields.IntegerField')()),
            ('current_major', self.gf('django.db.models.fields.IntegerField')()),
            ('current_minor', self.gf('django.db.models.fields.IntegerField')()),
        ))
        db.send_create_signal('Reporting', ['DeviceEntry'])

        # Adding model 'ServiceEntry'
        db.create_table('Reporting_serviceentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('hash_key', self.gf('django.db.models.fields.IntegerField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.IntegerField')()),
            ('exists', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('target_status', self.gf('django.db.models.fields.CharField')(default='', max_length=128)),
            ('current_status', self.gf('django.db.models.fields.CharField')(default='', max_length=128)),
        ))
        db.send_create_signal('Reporting', ['ServiceEntry'])


    def backwards(self, orm):
        # Removing unique constraint on 'FilePerms', fields ['owner', 'group', 'perms']
        db.delete_unique('Reporting_fileperms', ['owner', 'group', 'perms'])

        # Removing unique constraint on 'Interaction', fields ['client', 'timestamp']
        db.delete_unique('Reporting_interaction', ['client_id', 'timestamp'])

        # Deleting model 'Client'
        db.delete_table('Reporting_client')

        # Deleting model 'Interaction'
        db.delete_table('Reporting_interaction')

        # Removing M2M table for field actions on 'Interaction'
        db.delete_table('Reporting_interaction_actions')

        # Removing M2M table for field packages on 'Interaction'
        db.delete_table('Reporting_interaction_packages')

        # Removing M2M table for field paths on 'Interaction'
        db.delete_table('Reporting_interaction_paths')

        # Removing M2M table for field services on 'Interaction'
        db.delete_table('Reporting_interaction_services')

        # Removing M2M table for field failures on 'Interaction'
        db.delete_table('Reporting_interaction_failures')

        # Removing M2M table for field groups on 'Interaction'
        db.delete_table('Reporting_interaction_groups')

        # Removing M2M table for field bundles on 'Interaction'
        db.delete_table('Reporting_interaction_bundles')

        # Deleting model 'Performance'
        db.delete_table('Reporting_performance')

        # Deleting model 'Group'
        db.delete_table('Reporting_group')

        # Removing M2M table for field groups on 'Group'
        db.delete_table('Reporting_group_groups')

        # Removing M2M table for field bundles on 'Group'
        db.delete_table('Reporting_group_bundles')

        # Deleting model 'Bundle'
        db.delete_table('Reporting_bundle')

        # Deleting model 'FilePerms'
        db.delete_table('Reporting_fileperms')

        # Deleting model 'FileAcl'
        db.delete_table('Reporting_fileacl')

        # Deleting model 'FailureEntry'
        db.delete_table('Reporting_failureentry')

        # Deleting model 'ActionEntry'
        db.delete_table('Reporting_actionentry')

        # Deleting model 'PackageEntry'
        db.delete_table('Reporting_packageentry')

        # Deleting model 'PathEntry'
        db.delete_table('Reporting_pathentry')

        # Removing M2M table for field acls on 'PathEntry'
        db.delete_table('Reporting_pathentry_acls')

        # Deleting model 'LinkEntry'
        db.delete_table('Reporting_linkentry')

        # Deleting model 'DeviceEntry'
        db.delete_table('Reporting_deviceentry')

        # Deleting model 'ServiceEntry'
        db.delete_table('Reporting_serviceentry')


    models = {
        'Reporting.actionentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'ActionEntry'},
            'exists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hash_key': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'output': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'state': ('django.db.models.fields.IntegerField', [], {}),
            'status': ('django.db.models.fields.CharField', [], {'default': "'check'", 'max_length': '128'})
        },
        'Reporting.bundle': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Bundle'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
        },
        'Reporting.client': {
            'Meta': {'object_name': 'Client'},
            'creation': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'current_interaction': ('django.db.models.fields.related.ForeignKey', [], {'blank': 'True', 'related_name': "'parent_client'", 'null': 'True', 'to': "orm['Reporting.Interaction']"}),
            'expiration': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        'Reporting.deviceentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'DeviceEntry', '_ormbases': ['Reporting.PathEntry']},
            'current_major': ('django.db.models.fields.IntegerField', [], {}),
            'current_minor': ('django.db.models.fields.IntegerField', [], {}),
            'device_type': ('django.db.models.fields.CharField', [], {'max_length': '16'}),
            'pathentry_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['Reporting.PathEntry']", 'unique': 'True', 'primary_key': 'True'}),
            'target_major': ('django.db.models.fields.IntegerField', [], {}),
            'target_minor': ('django.db.models.fields.IntegerField', [], {})
        },
        'Reporting.failureentry': {
            'Meta': {'object_name': 'FailureEntry'},
            'entry_type': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'hash_key': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'message': ('django.db.models.fields.TextField', [], {}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'})
        },
        'Reporting.fileacl': {
            'Meta': {'object_name': 'FileAcl'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'})
        },
        'Reporting.fileperms': {
            'Meta': {'unique_together': "(('owner', 'group', 'perms'),)", 'object_name': 'FilePerms'},
            'group': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'owner': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'perms': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        'Reporting.group': {
            'Meta': {'ordering': "('name',)", 'object_name': 'Group'},
            'bundles': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.Bundle']", 'symmetrical': 'False'}),
            'category': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'comment': ('django.db.models.fields.TextField', [], {'blank': 'True'}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.Group']", 'symmetrical': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'profile': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'public': ('django.db.models.fields.BooleanField', [], {'default': 'False'})
        },
        'Reporting.interaction': {
            'Meta': {'ordering': "['-timestamp']", 'unique_together': "(('client', 'timestamp'),)", 'object_name': 'Interaction'},
            'actions': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.ActionEntry']", 'symmetrical': 'False'}),
            'bad_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'bundles': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.Bundle']", 'symmetrical': 'False'}),
            'client': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'interactions'", 'to': "orm['Reporting.Client']"}),
            'extra_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'failures': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.FailureEntry']", 'symmetrical': 'False'}),
            'good_count': ('django.db.models.fields.IntegerField', [], {}),
            'groups': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.Group']", 'symmetrical': 'False'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'modified_count': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'packages': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.PackageEntry']", 'symmetrical': 'False'}),
            'paths': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.PathEntry']", 'symmetrical': 'False'}),
            'profile': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'to': "orm['Reporting.Group']"}),
            'repo_rev_code': ('django.db.models.fields.CharField', [], {'max_length': '64'}),
            'server': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'services': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.ServiceEntry']", 'symmetrical': 'False'}),
            'state': ('django.db.models.fields.CharField', [], {'max_length': '32'}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {'db_index': 'True'}),
            'total_count': ('django.db.models.fields.IntegerField', [], {})
        },
        'Reporting.linkentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'LinkEntry', '_ormbases': ['Reporting.PathEntry']},
            'current_path': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'}),
            'pathentry_ptr': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['Reporting.PathEntry']", 'unique': 'True', 'primary_key': 'True'}),
            'target_path': ('django.db.models.fields.CharField', [], {'max_length': '1024', 'blank': 'True'})
        },
        'Reporting.packageentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'PackageEntry'},
            'current_version': ('django.db.models.fields.CharField', [], {'max_length': '1024'}),
            'exists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hash_key': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'state': ('django.db.models.fields.IntegerField', [], {}),
            'target_version': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '1024'}),
            'verification_details': ('django.db.models.fields.TextField', [], {'default': "''"})
        },
        'Reporting.pathentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'PathEntry'},
            'acls': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.FileAcl']", 'symmetrical': 'False'}),
            'current_perms': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'to': "orm['Reporting.FilePerms']"}),
            'detail_type': ('django.db.models.fields.IntegerField', [], {'default': '0'}),
            'details': ('django.db.models.fields.TextField', [], {'default': "''"}),
            'exists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hash_key': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'path_type': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'state': ('django.db.models.fields.IntegerField', [], {}),
            'target_perms': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'to': "orm['Reporting.FilePerms']"})
        },
        'Reporting.performance': {
            'Meta': {'object_name': 'Performance'},
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'interaction': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'performance_items'", 'to': "orm['Reporting.Interaction']"}),
            'metric': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'value': ('django.db.models.fields.DecimalField', [], {'max_digits': '32', 'decimal_places': '16'})
        },
        'Reporting.serviceentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'ServiceEntry'},
            'current_status': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128'}),
            'exists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hash_key': ('django.db.models.fields.IntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'state': ('django.db.models.fields.IntegerField', [], {}),
            'target_status': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128'})
        }
    }

    complete_apps = ['Reporting']