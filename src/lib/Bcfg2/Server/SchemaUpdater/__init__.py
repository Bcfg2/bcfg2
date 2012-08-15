from django.db import connection, DatabaseError
from django.core.exceptions import ImproperlyConfigured
import django.core.management
import logging
import pkgutil
import re
import sys
import traceback

from Bcfg2.Server.models import InternalDatabaseVersion
from Bcfg2.Server.SchemaUpdater.Routines import UpdaterRoutineException, \
                UpdaterRoutine
from Bcfg2.Server.SchemaUpdater import Changes

logger = logging.getLogger(__name__)

class UpdaterError(Exception):
    pass


class SchemaTooOldError(UpdaterError):
    pass


def _walk_packages(path):
    """Python 2.4 lacks this routine"""
    import glob
    submodules = []
    for path in __path__:
        for submodule in glob.glob("%s/*.py" % path):
            mod = '.'.join(submodule.split("/")[-1].split('.')[:-1])
            if mod != '__init__':
                submodules.append((None, mod, False))
    return submodules


def _release_to_version(release):
    """
    Build a release base for a version

    Expects a string of the form 00.00

    returns an integer of the form MMmm00
    """
    regex = re.compile("^(\d+)\.(\d+)$")
    m = regex.match(release)
    if not m:
        logger.error("Invalid release string: %s" % release)
        raise TypeError
    return int("%02d%02d00" % (int(m.group(1)), int(m.group(2))))


class Updater(object):
    """Database updater to standardize updates"""

    def __init__(self, release):
        self._cursor = None
        self._release = release
        try:
            self._base_version = _release_to_version(release)
        except:
            err = "Invalid release string: %s" % release
            logger.error(err)
            raise UpdaterError(err)

        self._fixes = []
        self._version = -1

    def __cmp__(self, other):
        return self._base_version - other._base_version

    @property
    def release(self):
        return self._release

    @property
    def version(self):
        if self._version < 0:
            try:
                iv = InternalDatabaseVersion.objects.latest()
                self._version = iv.version
            except InternalDatabaseVersion.DoesNotExist:
                raise UpdaterError("No database version stored internally")
        return self._version

    @property
    def cursor(self):
        if not self._cursor:
            self._cursor = connection.cursor()
        return self._cursor

    @property
    def target_version(self):
        if(len(self._fixes) == 0):
            return self._base_version
        else:
            return self._base_version + len(self._fixes) - 1


    def add(self, update):
        if type(update) == str or isinstance(update, UpdaterRoutine):
            self._fixes.append(update)
        else:
            raise TypeError


    def override_base_version(self, version):
        """Override our starting point for old releases.  New code should
           not use this method"""
        self._base_version = int(version)


    @staticmethod
    def get_current_version():
        """Queries the db for the latest version.  Returns 0 for a
        fresh install"""

        if "call_command" in dir(django.core.management):
            django.core.management.call_command("syncdb", interactive=False,
                                                verbosity=0)
        else:
            msg = "Unable to call syndb routine"
            logger.warning(msg)
            raise UpdaterError(msg)

        try:
            iv = InternalDatabaseVersion.objects.latest()
            version = iv.version
        except InternalDatabaseVersion.DoesNotExist:
            version = 0

        return version


    def syncdb(self):
        """Function to do the syncronisation for the models"""

        self._version = Updater.get_current_version()
        self._cursor = None


    def increment(self):
        """Increment schema version in the database"""
        if self._version < self._base_version:
            self._version = self._base_version
        else:
            self._version += 1
        InternalDatabaseVersion.objects.create(version=self._version)

    def apply(self):
        """Apply pending schema changes"""

        if self.version >= self.target_version:
            logger.debug("No updates for release %s" % self._release)
            return

        logger.debug("Applying updates for release %s" % self._release)

        if self.version < self._base_version:
            start = 0
        else:
            start = self.version - self._base_version + 1

        try:
            for fix in self._fixes[start:]:
                if type(fix) == str:
                    self.cursor.execute(fix)
                elif isinstance(fix, UpdaterRoutine):
                    fix.run()
                else:
                    logger.error("Invalid schema change at %s" % \
                        self._version + 1)
                self.increment()
                logger.debug("Applied schema change number %s: %s" % \
                    (self.version, fix))
            logger.info("Applied schema changes for release %s" % self._release)
        except:
            msg = "Failed to perform db update %s (%s): %s" % \
                (self._version + 1, fix,
                 traceback.format_exc().splitlines()[-1])
            logger.error(msg)
            raise UpdaterError(msg)


class UnsupportedUpdate(Updater):
    """Handle an unsupported update"""

    def __init__(self, release, version):
        super(UnsupportedUpdate, self).__init__(release)
        self._base_version = version

    def apply(self):
        """Raise an exception if we're too old"""

        if self.version < self.target_version:
            logger.error("Upgrade from release %s unsupported" % self._release)
            raise SchemaTooOldError


def update_database():
    """method to search where we are in the revision
    of the database models and update them"""
    try:
        logger.debug("Verifying database schema")

        updaters = []
        if hasattr(pkgutil, 'walk_packages'):
            submodules = pkgutil.walk_packages(path=Changes.__path__)
        else:
            #python 2.4
            submodules = _walk_packages(Changes.__path__)
        for loader, submodule, ispkg in submodules:
            if ispkg:
                continue
            try:
                updates = getattr(
                    __import__("%s.%s" % (Changes.__name__, submodule), 
                        globals(), locals(), ['*']),
                    "updates")
                updaters.append(updates())
            except ImportError:
                logger.error("Failed to import %s" % submodule)
            except AttributeError:
                logger.warning("Module %s does not have an updates function" %
                               submodule)
            except:
                msg = "Failed to build updater for %s" % submodule
                logger.error(msg, exc_info=1)
                raise UpdaterError(msg)

        current_version = Updater.get_current_version()
        logger.debug("Database version at %s" % current_version)

        if current_version > 0:
            [u.apply() for u in sorted(updaters)]
            logger.debug("Database version at %s" %
                         Updater.get_current_version())
        else:
            target = updaters[-1].target_version
            InternalDatabaseVersion.objects.create(version=target)
            logger.info("A new database was created")

    except UpdaterError:
        raise
    except ImproperlyConfigured:
        logger.error("Django is not properly configured: %s" %
                     traceback.format_exc().splitlines()[-1])
        raise UpdaterError
    except:
        logger.error("Error while updating the database")
        for x in traceback.format_exc().splitlines():
            logger.error(x)
        raise UpdaterError
