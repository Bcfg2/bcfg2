import sys
import atexit
import daemon
import logging
import time
import threading

# pylint: disable=E0611
try:
    from lockfile.pidlockfile import PIDLockFile
    from lockfile import Error as PIDFileError
except ImportError:
    from daemon.pidlockfile import PIDLockFile, PIDFileError
# pylint: enable=E0611

import Bcfg2.Logger
import Bcfg2.Options
from Bcfg2.Reporting.Transport.base import TransportError
from Bcfg2.Reporting.Transport.DirectStore import DirectStore
from Bcfg2.Reporting.Storage.base import StorageError



class ReportingError(Exception):
    """Generic reporting exception"""
    pass


class ReportingStoreThread(threading.Thread):
    """Thread for calling the storage backend"""
    def __init__(self, interaction, storage, group=None, target=None,
                 name=None, args=(), kwargs=None):
        """Initialize the thread with a reference to the interaction
        as well as the storage engine to use"""
        threading.Thread.__init__(self, group, target, name, args,
                                  kwargs or dict())
        self.interaction = interaction
        self.storage = storage
        self.logger = logging.getLogger('bcfg2-report-collector')

    def run(self):
        """Call the database storage procedure (aka import)"""
        try:
            start = time.time()
            self.storage.import_interaction(self.interaction)
            self.logger.info("Imported interaction for %s in %ss" %
                             (self.interaction.get('hostname', '<unknown>'),
                              time.time() - start))
        except:
            #TODO requeue?
            self.logger.error("Unhandled exception in import thread %s" %
                              traceback.format_exc().splitlines()[-1])


class ReportingCollector(object):
    """The collecting process for reports"""
    options = [Bcfg2.Options.Common.reporting_storage,
               Bcfg2.Options.Common.reporting_transport,
               Bcfg2.Options.Common.daemon]

    def __init__(self):
        """Setup the collector.  This may be called by the daemon or though
        bcfg2-admin"""
        self.terminate = None
        self.context = None

        if Bcfg2.Options.setup.debug:
            level = logging.DEBUG
        elif Bcfg2.Options.setup.verbose:
            level = logging.INFO
        else:
            level = logging.WARNING

        Bcfg2.Logger.setup_logging()
        self.logger = logging.getLogger('bcfg2-report-collector')

        try:
            self.transport = Bcfg2.Options.setup.reporting_transport()
            self.storage = Bcfg2.Options.setup.reporting_storage()
        except TransportError:
            self.logger.error("Failed to load transport: %s" %
                              sys.exc_info()[1])
            raise ReportingError
        except StorageError:
            self.logger.error("Failed to load storage: %s" %
                              sys.exc_info()[1])
            raise ReportingError

        if isinstance(self.transport, DirectStore):
            self.logger.error("DirectStore cannot be used with the collector. "
                              "Use LocalFilesystem instead")
            self.shutdown()
            raise ReportingError

        try:
            self.logger.debug("Validating storage %s" %
                              self.storage.__class__.__name__)
            self.storage.validate()
        except:
            self.logger.error("Storage backed %s failed to validate: %s" %
                              (self.storage.__class__.__name__,
                               sys.exc_info()[1]))

    def run(self):
        """Startup the processing and go!"""
        self.terminate = threading.Event()
        atexit.register(self.shutdown)
        self.context = daemon.DaemonContext(detach_process=True)

        if Bcfg2.Options.setup.daemon:
            self.logger.debug("Daemonizing")
            try:
                self.context.pidfile = PIDLockFile(Bcfg2.Options.setup.daemon)
                self.context.open()
            except PIDFileError:
                self.logger.error("Error writing pid file: %s" %
                                  sys.exc_info()[1])
                self.shutdown()
                return
            self.logger.info("Starting daemon")

        self.transport.start_monitor(self)

        while not self.terminate.isSet():
            try:
                interaction = self.transport.fetch()
                if not interaction:
                    continue
                store_thread = ReportingStoreThread(interaction, self.storage)
                store_thread.start()
            except (SystemExit, KeyboardInterrupt):
                self.logger.info("Shutting down")
                self.shutdown()
            except:
                self.logger.error("Unhandled exception in main loop %s" %
                                  sys.exc_info()[1])

    def shutdown(self):
        """Cleanup and go"""
        if self.terminate:
            # this wil be missing if called from bcfg2-admin
            self.terminate.set()
        if self.transport:
            try:
                self.transport.shutdown()
            except OSError:
                pass
        if self.storage:
            self.storage.shutdown()
