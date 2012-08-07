"""
1_1_x.py

This file should contain updates relevant to the 1.1.x branches ONLY.
The updates() method must be defined and it should return an Updater object
"""
from Bcfg2.Server.SchemaUpdater import Updater
from Bcfg2.Server.SchemaUpdater.Routines import updatercallable

from django.db import connection
import sys
import Bcfg2.settings
from Bcfg2.Server.Reports.reports.models import \
                TYPE_BAD, TYPE_MODIFIED, TYPE_EXTRA

@updatercallable
def _interactions_constraint_or_idx():
    """sqlite doesn't support alter tables.. or constraints"""
    cursor = connection.cursor()
    try:
        cursor.execute('alter table reports_interaction add constraint reports_interaction_20100601 unique (client_id,timestamp)')
    except:
        cursor.execute('create unique index reports_interaction_20100601 on reports_interaction (client_id,timestamp)')


@updatercallable
def _populate_interaction_entry_counts():
    '''Populate up the type totals for the interaction table'''
    cursor = connection.cursor()
    count_field = {TYPE_BAD: 'bad_entries',
                   TYPE_MODIFIED: 'modified_entries',
                   TYPE_EXTRA: 'extra_entries'}

    for type in list(count_field.keys()):
        cursor.execute("select count(type), interaction_id " +
                "from reports_entries_interactions where type = %s group by interaction_id" % type)
        updates = []
        for row in cursor.fetchall():
            updates.append(row)
        try:
            cursor.executemany("update reports_interaction set " + count_field[type] + "=%s where id = %s", updates)
        except Exception:
            e = sys.exc_info()[1]
            print(e)
    cursor.close()


def updates():
    fixes = Updater("1.1")
    fixes.override_base_version(12) # Do not do this in new code

    fixes.add('alter table reports_interaction add column bad_entries integer not null default -1;')
    fixes.add('alter table reports_interaction add column modified_entries integer not null default -1;')
    fixes.add('alter table reports_interaction add column extra_entries integer not null default -1;')
    fixes.add(_populate_interaction_entry_counts())
    fixes.add(_interactions_constraint_or_idx())
    fixes.add('alter table reports_reason add is_binary bool NOT NULL default False;')
    return fixes

