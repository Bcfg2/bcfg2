import atexit
import daemon
import logging
import time
import traceback
import threading

# pylint: disable=E0611
try:
    from lockfile.pidlockfile import PIDLockFile
    from lockfile import Error as PIDFileError
except ImportError:
    from daemon.pidlockfile import PIDLockFile, PIDFileError
# pylint: enable=E0611

import Bcfg2.Logger
from Bcfg2.Reporting.Transport import load_transport_from_config, \
    TransportError, TransportImportError
from Bcfg2.Reporting.Transport.DirectStore import DirectStore
from Bcfg2.Reporting.Storage import load_storage_from_config, \
    StorageError, StorageImportError

class ReportingError(Exception):
    """Generic reporting exception"""
    pass

class ReportingCollector(object):
    """The collecting process for reports"""

    def __init__(self, setup):
        """Setup the collector.  This may be called by the daemon or though 
        bcfg2-admin"""
        self.setup = setup
        self.datastore = setup['repo']
        self.encoding = setup['encoding']
        self.terminate = None
        self.context = None

        if setup['debug']:
            level = logging.DEBUG
        elif setup['verbose']:
            level = logging.INFO
        else:
            level = logging.WARNING

        Bcfg2.Logger.setup_logging('bcfg2-report-collector',
                                   to_console=logging.INFO,
                                   to_syslog=setup['syslog'],
                                   to_file=setup['logging'],
                                   level=level)
        self.logger = logging.getLogger('bcfg2-report-collector')

        try:
            self.transport = load_transport_from_config(setup)
            self.storage = load_storage_from_config(setup)
        except TransportError:
            self.logger.error("Failed to load transport: %s" %
                traceback.format_exc().splitlines()[-1])
            raise ReportingError
        except StorageError:
            self.logger.error("Failed to load storage: %s" %
                traceback.format_exc().splitlines()[-1])
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
                    traceback.format_exc().splitlines()[-1]))


    def run(self):
        """Startup the processing and go!"""
        self.terminate = threading.Event()
        atexit.register(self.shutdown)
        self.context = daemon.DaemonContext()

        if self.setup['daemon']:
            self.logger.debug("Daemonizing")
            try:
                self.context.pidfile = PIDLockFile(self.setup['daemon'])
                self.context.open()
            except PIDFileError:
                self.logger.error("Error writing pid file: %s" %
                    traceback.format_exc().splitlines()[-1])
                self.shutdown()
                return
            self.logger.info("Starting daemon")

        self.transport.start_monitor(self)

        while not self.terminate.isSet():
            try:
                interaction = self.transport.fetch()
                if not interaction:
                    continue
                try:
                    start = time.time()
                    self.storage.import_interaction(interaction)
                    self.logger.info("Imported interaction for %s in %ss" %
                        (interaction.get('hostname', '<unknown>'),
                            time.time() - start))
                except:
                    #TODO requeue?
                    raise
            except (SystemExit, KeyboardInterrupt):
                self.logger.info("Shutting down")
                self.shutdown()
            except:
                self.logger.error("Unhandled exception in main loop %s" %
                    traceback.format_exc().splitlines()[-1])

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
