# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding model 'SELoginEntry'
        db.create_table('Reporting_seloginentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('hash_key', self.gf('django.db.models.fields.BigIntegerField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.IntegerField')()),
            ('exists', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('selinuxuser', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('current_selinuxuser', self.gf('django.db.models.fields.CharField')(max_length=128, null=True)),
        ))
        db.send_create_signal('Reporting', ['SELoginEntry'])

        # Adding model 'SEUserEntry'
        db.create_table('Reporting_seuserentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('hash_key', self.gf('django.db.models.fields.BigIntegerField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.IntegerField')()),
            ('exists', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('roles', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('current_roles', self.gf('django.db.models.fields.CharField')(max_length=128, null=True)),
            ('prefix', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('current_prefix', self.gf('django.db.models.fields.CharField')(max_length=128, null=True)),
        ))
        db.send_create_signal('Reporting', ['SEUserEntry'])

        # Adding model 'SEBooleanEntry'
        db.create_table('Reporting_sebooleanentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('hash_key', self.gf('django.db.models.fields.BigIntegerField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.IntegerField')()),
            ('exists', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('value', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal('Reporting', ['SEBooleanEntry'])

        # Adding model 'SENodeEntry'
        db.create_table('Reporting_senodeentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('hash_key', self.gf('django.db.models.fields.BigIntegerField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.IntegerField')()),
            ('exists', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('selinuxtype', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('current_selinuxtype', self.gf('django.db.models.fields.CharField')(max_length=128, null=True)),
            ('proto', self.gf('django.db.models.fields.CharField')(max_length=4)),
        ))
        db.send_create_signal('Reporting', ['SENodeEntry'])

        # Adding model 'SEFcontextEntry'
        db.create_table('Reporting_sefcontextentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('hash_key', self.gf('django.db.models.fields.BigIntegerField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.IntegerField')()),
            ('exists', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('selinuxtype', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('current_selinuxtype', self.gf('django.db.models.fields.CharField')(max_length=128, null=True)),
            ('filetype', self.gf('django.db.models.fields.CharField')(max_length=16)),
        ))
        db.send_create_signal('Reporting', ['SEFcontextEntry'])

        # Adding model 'SEInterfaceEntry'
        db.create_table('Reporting_seinterfaceentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('hash_key', self.gf('django.db.models.fields.BigIntegerField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.IntegerField')()),
            ('exists', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('selinuxtype', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('current_selinuxtype', self.gf('django.db.models.fields.CharField')(max_length=128, null=True)),
        ))
        db.send_create_signal('Reporting', ['SEInterfaceEntry'])

        # Adding model 'SEPermissiveEntry'
        db.create_table('Reporting_sepermissiveentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('hash_key', self.gf('django.db.models.fields.BigIntegerField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.IntegerField')()),
            ('exists', self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal('Reporting', ['SEPermissiveEntry'])

        # Adding model 'SEModuleEntry'
        db.create_table('Reporting_semoduleentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('hash_key', self.gf('django.db.models.fields.BigIntegerField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.IntegerField')()),
            ('exists', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('disabled', self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('current_disabled', self.gf('django.db.models.fields.BooleanField')(default=False)),
        ))
        db.send_create_signal('Reporting', ['SEModuleEntry'])

        # Adding model 'SEPortEntry'
        db.create_table('Reporting_seportentry', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=128, db_index=True)),
            ('hash_key', self.gf('django.db.models.fields.BigIntegerField')(db_index=True)),
            ('state', self.gf('django.db.models.fields.IntegerField')()),
            ('exists', self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('selinuxtype', self.gf('django.db.models.fields.CharField')(max_length=128)),
            ('current_selinuxtype', self.gf('django.db.models.fields.CharField')(max_length=128, null=True)),
        ))
        db.send_create_signal('Reporting', ['SEPortEntry'])

        # Adding M2M table for field sebooleans on 'Interaction'
        db.create_table('Reporting_interaction_sebooleans', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('sebooleanentry', models.ForeignKey(orm['Reporting.sebooleanentry'], null=False))
        ))
        db.create_unique('Reporting_interaction_sebooleans', ['interaction_id', 'sebooleanentry_id'])

        # Adding M2M table for field seports on 'Interaction'
        db.create_table('Reporting_interaction_seports', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('seportentry', models.ForeignKey(orm['Reporting.seportentry'], null=False))
        ))
        db.create_unique('Reporting_interaction_seports', ['interaction_id', 'seportentry_id'])

        # Adding M2M table for field sefcontexts on 'Interaction'
        db.create_table('Reporting_interaction_sefcontexts', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('sefcontextentry', models.ForeignKey(orm['Reporting.sefcontextentry'], null=False))
        ))
        db.create_unique('Reporting_interaction_sefcontexts', ['interaction_id', 'sefcontextentry_id'])

        # Adding M2M table for field senodes on 'Interaction'
        db.create_table('Reporting_interaction_senodes', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('senodeentry', models.ForeignKey(orm['Reporting.senodeentry'], null=False))
        ))
        db.create_unique('Reporting_interaction_senodes', ['interaction_id', 'senodeentry_id'])

        # Adding M2M table for field selogins on 'Interaction'
        db.create_table('Reporting_interaction_selogins', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('seloginentry', models.ForeignKey(orm['Reporting.seloginentry'], null=False))
        ))
        db.create_unique('Reporting_interaction_selogins', ['interaction_id', 'seloginentry_id'])

        # Adding M2M table for field seusers on 'Interaction'
        db.create_table('Reporting_interaction_seusers', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('seuserentry', models.ForeignKey(orm['Reporting.seuserentry'], null=False))
        ))
        db.create_unique('Reporting_interaction_seusers', ['interaction_id', 'seuserentry_id'])

        # Adding M2M table for field seinterfaces on 'Interaction'
        db.create_table('Reporting_interaction_seinterfaces', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('seinterfaceentry', models.ForeignKey(orm['Reporting.seinterfaceentry'], null=False))
        ))
        db.create_unique('Reporting_interaction_seinterfaces', ['interaction_id', 'seinterfaceentry_id'])

        # Adding M2M table for field sepermissives on 'Interaction'
        db.create_table('Reporting_interaction_sepermissives', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('sepermissiveentry', models.ForeignKey(orm['Reporting.sepermissiveentry'], null=False))
        ))
        db.create_unique('Reporting_interaction_sepermissives', ['interaction_id', 'sepermissiveentry_id'])

        # Adding M2M table for field semodules on 'Interaction'
        db.create_table('Reporting_interaction_semodules', (
            ('id', models.AutoField(verbose_name='ID', primary_key=True, auto_created=True)),
            ('interaction', models.ForeignKey(orm['Reporting.interaction'], null=False)),
            ('semoduleentry', models.ForeignKey(orm['Reporting.semoduleentry'], null=False))
        ))
        db.create_unique('Reporting_interaction_semodules', ['interaction_id', 'semoduleentry_id'])


    def backwards(self, orm):
        # Deleting model 'SELoginEntry'
        db.delete_table('Reporting_seloginentry')

        # Deleting model 'SEUserEntry'
        db.delete_table('Reporting_seuserentry')

        # Deleting model 'SEBooleanEntry'
        db.delete_table('Reporting_sebooleanentry')

        # Deleting model 'SENodeEntry'
        db.delete_table('Reporting_senodeentry')

        # Deleting model 'SEFcontextEntry'
        db.delete_table('Reporting_sefcontextentry')

        # Deleting model 'SEInterfaceEntry'
        db.delete_table('Reporting_seinterfaceentry')

        # Deleting model 'SEPermissiveEntry'
        db.delete_table('Reporting_sepermissiveentry')

        # Deleting model 'SEModuleEntry'
        db.delete_table('Reporting_semoduleentry')

        # Deleting model 'SEPortEntry'
        db.delete_table('Reporting_seportentry')

        # Removing M2M table for field sebooleans on 'Interaction'
        db.delete_table('Reporting_interaction_sebooleans')

        # Removing M2M table for field seports on 'Interaction'
        db.delete_table('Reporting_interaction_seports')

        # Removing M2M table for field sefcontexts on 'Interaction'
        db.delete_table('Reporting_interaction_sefcontexts')

        # Removing M2M table for field senodes on 'Interaction'
        db.delete_table('Reporting_interaction_senodes')

        # Removing M2M table for field selogins on 'Interaction'
        db.delete_table('Reporting_interaction_selogins')

        # Removing M2M table for field seusers on 'Interaction'
        db.delete_table('Reporting_interaction_seusers')

        # Removing M2M table for field seinterfaces on 'Interaction'
        db.delete_table('Reporting_interaction_seinterfaces')

        # Removing M2M table for field sepermissives on 'Interaction'
        db.delete_table('Reporting_interaction_sepermissives')

        # Removing M2M table for field semodules on 'Interaction'
        db.delete_table('Reporting_interaction_semodules')


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
            'sebooleans': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.SEBooleanEntry']", 'symmetrical': 'False'}),
            'sefcontexts': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.SEFcontextEntry']", 'symmetrical': 'False'}),
            'seinterfaces': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.SEInterfaceEntry']", 'symmetrical': 'False'}),
            'selogins': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.SELoginEntry']", 'symmetrical': 'False'}),
            'semodules': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.SEModuleEntry']", 'symmetrical': 'False'}),
            'senodes': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.SENodeEntry']", 'symmetrical': 'False'}),
            'sepermissives': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.SEPermissiveEntry']", 'symmetrical': 'False'}),
            'seports': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.SEPortEntry']", 'symmetrical': 'False'}),
            'server': ('django.db.models.fields.CharField', [], {'max_length': '256'}),
            'services': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.ServiceEntry']", 'symmetrical': 'False'}),
            'seusers': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['Reporting.SEUserEntry']", 'symmetrical': 'False'}),
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
        'Reporting.sebooleanentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'SEBooleanEntry'},
            'exists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hash_key': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'state': ('django.db.models.fields.IntegerField', [], {}),
            'value': ('django.db.models.fields.BooleanField', [], {'default': 'True'})
        },
        'Reporting.sefcontextentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'SEFcontextEntry'},
            'current_selinuxtype': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'exists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'filetype': ('django.db.models.fields.CharField', [], {'max_length': '16'}),
            'hash_key': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'selinuxtype': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'state': ('django.db.models.fields.IntegerField', [], {})
        },
        'Reporting.seinterfaceentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'SEInterfaceEntry'},
            'current_selinuxtype': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'exists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hash_key': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'selinuxtype': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'state': ('django.db.models.fields.IntegerField', [], {})
        },
        'Reporting.seloginentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'SELoginEntry'},
            'current_selinuxuser': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'exists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hash_key': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'selinuxuser': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'state': ('django.db.models.fields.IntegerField', [], {})
        },
        'Reporting.semoduleentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'SEModuleEntry'},
            'current_disabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'disabled': ('django.db.models.fields.BooleanField', [], {'default': 'False'}),
            'exists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hash_key': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'state': ('django.db.models.fields.IntegerField', [], {})
        },
        'Reporting.senodeentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'SENodeEntry'},
            'current_selinuxtype': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'exists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hash_key': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'proto': ('django.db.models.fields.CharField', [], {'max_length': '4'}),
            'selinuxtype': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'state': ('django.db.models.fields.IntegerField', [], {})
        },
        'Reporting.sepermissiveentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'SEPermissiveEntry'},
            'exists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hash_key': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'state': ('django.db.models.fields.IntegerField', [], {})
        },
        'Reporting.seportentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'SEPortEntry'},
            'current_selinuxtype': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'exists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hash_key': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'selinuxtype': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'state': ('django.db.models.fields.IntegerField', [], {})
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
        },
        'Reporting.seuserentry': {
            'Meta': {'ordering': "('state', 'name')", 'object_name': 'SEUserEntry'},
            'current_prefix': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'current_roles': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True'}),
            'exists': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'hash_key': ('django.db.models.fields.BigIntegerField', [], {'db_index': 'True'}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128', 'db_index': 'True'}),
            'prefix': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'roles': ('django.db.models.fields.CharField', [], {'max_length': '128'}),
            'state': ('django.db.models.fields.IntegerField', [], {})
        }
    }

    complete_apps = ['Reporting']