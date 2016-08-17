# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'MetadataClientModel'
        db.create_table(u'Server_metadataclientmodel', (
            ('hostname', self.gf('django.db.models.fields.CharField')(max_length=255, primary_key=True)),
            ('version', self.gf('django.db.models.fields.CharField')(max_length=31, null=True)),
        ))
        db.send_create_signal('Server', ['MetadataClientModel'])

        # Adding model 'ProbesDataModel'
        db.create_table(u'Server_probesdatamodel', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('hostname', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('probe', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('timestamp', self.gf('django.db.models.fields.DateTimeField')(auto_now=True, blank=True)),
            ('data', self.gf('django.db.models.fields.TextField')(null=True)),
        ))
        db.send_create_signal('Server', ['ProbesDataModel'])

        # Adding model 'ProbesGroupsModel'
        db.create_table(u'Server_probesgroupsmodel', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('hostname', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('group', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal('Server', ['ProbesGroupsModel'])


    def backwards(self, orm):
        # Deleting model 'MetadataClientModel'
        db.delete_table(u'Server_metadataclientmodel')

        # Deleting model 'ProbesDataModel'
        db.delete_table(u'Server_probesdatamodel')

        # Deleting model 'ProbesGroupsModel'
        db.delete_table(u'Server_probesgroupsmodel')


    models = {
        'Server.metadataclientmodel': {
            'Meta': {'object_name': 'MetadataClientModel'},
            'hostname': ('django.db.models.fields.CharField', [], {'max_length': '255', 'primary_key': 'True'}),
            'version': ('django.db.models.fields.CharField', [], {'max_length': '31', 'null': 'True'})
        },
        'Server.probesdatamodel': {
            'Meta': {'object_name': 'ProbesDataModel'},
            'data': ('django.db.models.fields.TextField', [], {'null': 'True'}),
            'hostname': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'probe': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'timestamp': ('django.db.models.fields.DateTimeField', [], {'auto_now': 'True', 'blank': 'True'})
        },
        'Server.probesgroupsmodel': {
            'Meta': {'object_name': 'ProbesGroupsModel'},
            'group': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'hostname': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        }
    }

    complete_apps = ['Server']