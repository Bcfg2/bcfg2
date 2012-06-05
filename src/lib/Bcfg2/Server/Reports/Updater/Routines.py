import logging
import traceback
from django.db.models.fields import NOT_PROVIDED
from django.db import connection, DatabaseError, backend, models
from django.core.management.color import no_style
from django.core.management.sql import sql_create
import django.core.management

import Bcfg2.Server.Reports.settings

logger = logging.getLogger(__name__)

def _quote(value):
    """
    Quote a string to use as a table name or column
    """
    return backend.DatabaseOperations().quote_name(value)


def _rebuild_sqlite_table(model):
    """Sqlite doesn't support most alter table statments.  This streamlines the
       rebuild process"""
    try:
        cursor = connection.cursor()
        table_name = model._meta.db_table

        # Build create staement from django
        model._meta.db_table = "%s_temp" % table_name
        sql, references = connection.creation.sql_create_model(model, no_style())
        columns = ",".join([_quote(f.column) \
                               for f in model._meta.fields])

        # Create a temp table
        [cursor.execute(s) for s in sql]

        # Fill the table
        tbl_name = _quote(table_name)
        tmp_tbl_name = _quote(model._meta.db_table)
        # Reset this
        model._meta.db_table = table_name
        cursor.execute("insert into %s(%s) select %s from %s;" % (
            tmp_tbl_name,
            columns,
            columns,
            tbl_name))
        cursor.execute("drop table %s" % tbl_name)

        # Call syncdb to create the table again
        django.core.management.call_command("syncdb", interactive=False, verbosity=0)
        # syncdb closes our cursor
        cursor = connection.cursor()
        # Repopulate
        cursor.execute('insert into %s(%s) select %s from %s;' % (tbl_name,
                                                                  columns,
                                                                  columns,
                                                                  tmp_tbl_name))
        cursor.execute('DROP TABLE %s;' % tmp_tbl_name)
    except DatabaseError:
        logger.error("Failed to rebuild sqlite table %s" % table_name, exc_info=1)
        raise UpdaterRoutineException


class UpdaterRoutineException(Exception):
    pass


class UpdaterRoutine(object):
    """Base for routines."""
    def __init__(self):
        pass

    def __str__(self):
        return __name__

    def run(self):
        """Called to execute the action"""
        raise UpdaterRoutineException



class AddColumns(UpdaterRoutine):
    """
    Routine to add new columns to an existing model
    """
    def __init__(self, model):
        self.model = model
        self.model_name = model.__name__

    def __str__(self):
        return "Add new columns for model %s" % self.model_name

    def run(self):
        try:
            cursor = connection.cursor()
        except DatabaseError:
            logger.error("Failed to connect to the db")
            raise UpdaterRoutineException

        try:
            desc = {}
            for d in connection.introspection.get_table_description(cursor, 
                    self.model._meta.db_table):
                desc[d[0]] = d
        except DatabaseError:
            logger.error("Failed to get table description", exc_info=1)
            raise UpdaterRoutineException

        for field in self.model._meta.fields:
            if field.column in desc:
                continue
            logger.debug("Column %s does not exist yet" % field.column)
            if field.default == NOT_PROVIDED:
                logger.error("Cannot add a column with out a default value")
                raise UpdaterRoutineException

            sql = "ALTER TABLE %s ADD %s %s NOT NULL DEFAULT " % (
                    _quote(self.model._meta.db_table),
                    _quote(field.column), field.db_type(), )
            db_engine = Bcfg2.Server.Reports.settings.DATABASES['default']['ENGINE']
            if db_engine == 'django.db.backends.sqlite3':
                sql += _quote(field.default)
                sql_values = ()
            else:
                sql += '%s'
                sql_values = (field.default, )
            try:
                cursor.execute(sql, sql_values)
                logger.debug("Added column %s to %s" % 
                        (field.column, self.model._meta.db_table))
            except DatabaseError:
                logger.error("Unable to add column %s" % field.column)
                raise UpdaterRoutineException


class RebuildTable(UpdaterRoutine):
    """
    Rebuild the table for an existing model.  Use this if field types have changed.
    """
    def __init__(self, model, columns):
        self.model = model
        self.model_name = model.__name__

        if type(columns) == str:
            self.columns = [columns]
        elif type(columns) in (tuple, list):
            self.columns = columns
        else:
            logger.error("Columns must be a str, tuple, or list")
            raise UpdaterRoutineException


    def __str__(self):
        return "Rebuild columns for model %s" % self.model_name

    def run(self):
        try:
            cursor = connection.cursor()
        except DatabaseError:
            logger.error("Failed to connect to the db")
            raise UpdaterRoutineException

        db_engine = Bcfg2.Server.Reports.settings.DATABASES['default']['ENGINE']
        if db_engine == 'django.db.backends.sqlite3':
            """ Sqlite is a special case.  Altering columns is not supported. """
            _rebuild_sqlite_table(self.model)
            return

        if db_engine == 'django.db.backends.mysql':
            modify_cmd = 'MODIFY '
        else:
            modify_cmd = 'ALTER COLUMN '

        col_strings = []
        for column in self.columns:
            col_strings.append("%s %s %s" % ( \
                modify_cmd,
                _quote(column),
                self.model._meta.get_field(column).db_type()
            ))

        try:
            cursor.execute('ALTER TABLE %s %s' %
                (_quote(self.model._meta.db_table), ", ".join(col_strings)))
        except DatabaseError:
            logger.debug("Failed modify table %s" % self.model._meta.db_table)
            raise UpdaterRoutineException



class RemoveColumns(RebuildTable):
    """
    Routine to remove columns from an existing model
    """
    def __init__(self, model, columns):
        super(RemoveColumns, self).__init__(model, columns)


    def __str__(self):
        return "Remove columns from model %s" % self.model_name

    def run(self):
        try:
            cursor = connection.cursor()
        except DatabaseError:
            logger.error("Failed to connect to the db")
            raise UpdaterRoutineException

        try:
            columns = [d[0] for d in connection.introspection.get_table_description(cursor, 
                    self.model._meta.db_table)]
        except DatabaseError:
            logger.error("Failed to get table description", exc_info=1)
            raise UpdaterRoutineException

        for column in self.columns:
            if column not in columns:
                logger.warning("Cannot drop column %s: does not exist" % column)
                continue

            logger.debug("Dropping column %s" % column)

            db_engine = Bcfg2.Server.Reports.settings.DATABASES['default']['ENGINE']
            if db_engine == 'django.db.backends.sqlite3':
                _rebuild_sqlite_table(self.model)
            else:
                sql = "alter table %s drop column %s" % \
                    (_quote(self.model._meta.db_table), _quote(column), )
                try:
                    cursor.execute(sql)
                except DatabaseError:
                    logger.debug("Failed to drop column %s from %s" % 
                        (column, self.model._meta.db_table))
                    raise UpdaterRoutineException


class DropTable(UpdaterRoutine):
    """
    Drop a table
    """
    def __init__(self, table_name):
        self.table_name = table_name

    def __str__(self):
        return "Drop table %s" % self.table_name

    def run(self):
        try:
            cursor = connection.cursor()
            cursor.execute('DROP TABLE %s' % _quote(self.table_name))
        except DatabaseError:
            logger.error("Failed to drop table: %s" % 
                    traceback.format_exc().splitlines()[-1])
            raise UpdaterRoutineException


class UpdaterCallable(UpdaterRoutine):
    """Helper for routines.  Basically delays execution"""
    def __init__(self, fn):
        self.fn = fn
        self.args = []
        self.kwargs = {}

    def __call__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        return self

    def __str__(self):
        return self.fn.__name__

    def run(self):
        self.fn(*self.args, **self.kwargs)

def updatercallable(fn):
    """Decorator for UpdaterCallable.  Use for any function passed
       into the fixes list"""
    return UpdaterCallable(fn)


