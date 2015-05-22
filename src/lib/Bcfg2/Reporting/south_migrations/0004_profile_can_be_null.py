# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):

        # Changing field 'Interaction.profile'
        db.alter_column('Reporting_interaction', 'profile_id', self.gf('django.db.models.fields.related.ForeignKey')(null=True, to=orm['Reporting.Group']))

    def backwards(self, orm):

        # User chose to not deal with backwards NULL issues for 'Interaction.profile'
        raise RuntimeError("Cannot reverse this migration. 'Interaction.profile' and its values cannot be restored.")

    models = {
        'Reporting.actionentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'ActionEntry'},
            'exists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hash_key': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
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
            'hash_key': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
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
            'Meta': {'unique_together': "(('owner', 'group', 'mode'),)", 'object_name': 'FilePerms'},
            'group': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'mode': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'owner': ('django.db.models.fields.CharField', [], {'max_length': '128'})
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
            'profile': ('django.db.models.fields.related.ForeignKey', [], {'related_name': "'+'", 'null': 'True', 'to': "orm['Reporting.Group']"}),
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
            'hash_key': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
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
            'hash_key': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
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
            'hash_key': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'state': ('django.db.models.fields.IntegerField', [], {}),
            'target_status': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '128'})
        }
    }

    complete_apps = ['Reporting']