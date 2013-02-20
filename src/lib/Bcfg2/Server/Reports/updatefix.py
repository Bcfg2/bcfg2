import Bcfg2.settings

from django.db import connection
import django.core.management
import sys
import logging
import traceback
from Bcfg2.Server.models import InternalDatabaseVersion
logger = logging.getLogger('Bcfg2.Server.Reports.UpdateFix')


# all update function should go here
def _merge_database_table_entries():
    cursor = connection.cursor()
    insert_cursor = connection.cursor()
    find_cursor = connection.cursor()
    cursor.execute("""
    Select name, kind from reports_bad
    union 
    select name, kind from reports_modified
    union 
    select name, kind from reports_extra
    """)
    # this fetch could be better done
    entries_map = {}
    for row in cursor.fetchall():
        insert_cursor.execute("insert into reports_entries (name, kind) \
            values (%s, %s)", (row[0], row[1]))
        entries_map[(row[0], row[1])] = insert_cursor.lastrowid

    cursor.execute("""
        Select name, kind, reason_id, interaction_id, 1 from reports_bad
        inner join reports_bad_interactions on reports_bad.id=reports_bad_interactions.bad_id
        union
        Select name, kind, reason_id, interaction_id, 2 from reports_modified
        inner join reports_modified_interactions on reports_modified.id=reports_modified_interactions.modified_id
        union
        Select name, kind, reason_id, interaction_id, 3 from reports_extra
        inner join reports_extra_interactions on reports_extra.id=reports_extra_interactions.extra_id
    """)
    for row in cursor.fetchall():
        key = (row[0], row[1])
        if entries_map.get(key, None):
            entry_id = entries_map[key]
        else:
            find_cursor.execute("Select id from reports_entries where name=%s and kind=%s", key)
            rowe = find_cursor.fetchone()
            entry_id = rowe[0]
        insert_cursor.execute("insert into reports_entries_interactions \
            (entry_id, interaction_id, reason_id, type) values (%s, %s, %s, %s)", (entry_id, row[3], row[2], row[4]))


def _interactions_constraint_or_idx():
    '''sqlite doesn't support alter tables.. or constraints'''
    cursor = connection.cursor()
    try:
        cursor.execute('alter table reports_interaction add constraint reports_interaction_20100601 unique (client_id,timestamp)')
    except:
        cursor.execute('create unique index reports_interaction_20100601 on reports_interaction (client_id,timestamp)')


def _populate_interaction_entry_counts():
    '''Populate up the type totals for the interaction table'''
    cursor = connection.cursor()
    count_field = {1: 'bad_entries',
                   2: 'modified_entries',
                   3: 'extra_entries'}

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


def update_noop():
    return True

# be sure to test your upgrade query before reflecting the change in the models
# the list of function and sql command to do should go here
_fixes = [_merge_database_table_entries,
          # this will remove unused tables
          "drop table reports_bad;",
          "drop table reports_bad_interactions;",
          "drop table reports_extra;",
          "drop table reports_extra_interactions;",
          "drop table reports_modified;",
          "drop table reports_modified_interactions;",
          "drop table reports_repository;",
          "drop table reports_metadata;",
          "alter table reports_interaction add server varchar(256) not null default 'N/A';",
          # fix revision data type to support $VCS hashes
          "alter table reports_interaction add repo_rev_code varchar(64) default '';",
          # Performance enhancements for large sites
          'alter table reports_interaction add column bad_entries integer not null default -1;',
          'alter table reports_interaction add column modified_entries integer not null default -1;',
          'alter table reports_interaction add column extra_entries integer not null default -1;',
          _populate_interaction_entry_counts,
          _interactions_constraint_or_idx,
          'alter table reports_reason add is_binary bool NOT NULL default False;',
          'alter table reports_reason add is_sensitive bool NOT NULL default False;',
          update_noop, #_remove_table_column('reports_interaction', 'client_version'),
          "alter table reports_reason add unpruned varchar(1280) not null default 'N/A';",
]

# this will calculate the last possible version of the database
lastversion = len(_fixes)


def rollupdate(current_version):
    """ function responsible to coordinates all the updates
    need current_version as integer
    """
    ret = None
    if current_version < lastversion:
        for i in range(current_version, lastversion):
            try:
                if type(_fixes[i]) == str:
                    connection.cursor().execute(_fixes[i])
                else:
                    _fixes[i]()
            except:
                logger.error("Failed to perform db update %s" % (_fixes[i]), exc_info=1)
            # since array start at 0 but version start at 1 we add 1 to the normal count
            ret = InternalDatabaseVersion.objects.create(version=i + 1)
        return ret
    else:
        return None


def update_database():
    ''' methode to search where we are in the revision of the database models and update them '''
    try:
        logger.debug("Running upgrade of models to the new one")
        django.core.management.call_command("syncdb", interactive=False, verbosity=0)
        know_version = InternalDatabaseVersion.objects.order_by('-version')
        if not know_version:
            logger.debug("No version, creating initial version")
            know_version = InternalDatabaseVersion.objects.create(version=lastversion)
        else:
            know_version = know_version[0]
        logger.debug("Presently at %s" % know_version)
        if know_version.version > 13000:
            # SchemaUpdater stuff
            return
        elif know_version.version < lastversion:
            new_version = rollupdate(know_version.version)
            if new_version:
                logger.debug("upgraded to %s" % new_version)
    except:
        logger.error("Error while updating the database")
        for x in traceback.format_exc().splitlines():
            logger.error(x)
