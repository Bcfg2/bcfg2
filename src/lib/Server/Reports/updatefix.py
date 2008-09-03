import Bcfg2.Server.Reports.settings

from django.db import connection
import django.core.management
from Bcfg2.Server.Reports.reports.models import InternalDatabaseVersion

import logging, traceback
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
    entries_map={}
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
]

# this will calculate the last possible version of the database
lastversion = len(_fixes)

def rollupdate(current_version):
    """ function responsible to coordinates all the updates
    need current_version as integer
    """
    if current_version < lastversion:
        for i in range(current_version, lastversion):
            if type(_fixes[i]) == str:
                connection.cursor().execute(_fixes[i])
            else:
                _fixes[i]()
            # since array start at 0 but version start at 1 we add 1 to the normal count
            ret = InternalDatabaseVersion.objects.create(version=i+1)
        return ret
    else:
        return None

def dosync():
    """Function to do the syncronisation for the models"""
    # try to detect if it's a fresh new database
    try:
        cursor = connection.cursor()
        # If this table goes missing then don't forget to change it to the new one
        cursor.execute("Select * from reports_client")
        # if we get here with no error then the database has existing tables
        fresh = False
    except:
        logger.debug("there was an error while detecting the freshnest of the database")
        #we should get here if the database is new
        fresh = True

    # ensure database connection are close, so that the management can do it's job right    
    cursor.close()
    connection.close()
    # Do the syncdb according to the django version
    if "call_command" in dir(django.core.management):
        # this is available since django 1.0 alpha.
        # not yet tested for full functionnality
        django.core.management.call_command("syncdb", interactive=False, verbosity=0)
        if fresh:
            django.core.management.call_command("loaddata", fixture_labels=['initial_version'], verbosity=0)
    elif "syncdb" in dir(django.core.management):
        # this exist only for django 0.96.*
        django.core.management.syncdb(interactive=False, verbosity=0)
        if fresh:
            logger.debug("loading the initial_version fixtures")
            django.core.management.load_data(fixture_labels=['initial_version'], verbosity=0)
    else:
        logger.warning("Don't forget to run syncdb")


def update_database():
    ''' methode to search where we are in the revision of the database models and update them '''
    try :
        logger.debug("Running upgrade of models to the new one")
        dosync()
        know_version = InternalDatabaseVersion.objects.order_by('-version')
        if not know_version:
            logger.debug("No version, creating initial version")
            know_version = InternalDatabaseVersion.objects.create(version=0)
        else:
            know_version = know_version[0]
        logger.debug("Presently at %s" % know_version)
        if know_version.version < lastversion:
            new_version = rollupdate(know_version.version)
            if new_version:
                logger.debug("upgraded to %s" % new_version)
    except:
        logger.error("Error while updating the database")
        for x in traceback.format_exc().splitlines():
            logger.error(x)
