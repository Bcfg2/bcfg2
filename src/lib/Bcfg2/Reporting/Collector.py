import os
import sys
import atexit
import daemon
import logging
import time
import threading

from lockfile import LockFailed, LockTimeout
# pylint: disable=E0611
try:
    from daemon.pidfile import TimeoutPIDLockFile
except ImportError:
    from daemon.pidlockfile import TimeoutPIDLockFile
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
                 name=None, semaphore=None, args=(), kwargs=None):
        """Initialize the thread with a reference to the interaction
        as well as the storage engine to use"""
        threading.Thread.__init__(self, group, target, name, args,
                                  kwargs or dict())
        self.interaction = interaction
        self.storage = storage
        self.logger = logging.getLogger('bcfg2-report-collector')
        self.semaphore = semaphore

    def run(self):
        """Call the database storage procedure (aka import)"""
        try:
            try:
                start = time.time()
                self.storage.import_interaction(self.interaction)
                self.logger.info("Imported interaction for %s in %ss" %
                                 (self.interaction.get('hostname',
                                                       '<unknown>'),
                                  time.time() - start))
            except:
                #TODO requeue?
                self.logger.error("Unhandled exception in import thread %s" %
                                  sys.exc_info()[1])
        finally:
            if self.semaphore:
                self.semaphore.release()


class ReportingCollector(object):
    """The collecting process for reports"""
    options = [Bcfg2.Options.Common.reporting_storage,
               Bcfg2.Options.Common.reporting_transport,
               Bcfg2.Options.Common.daemon,
               Bcfg2.Options.Option(
                   '--max-children', dest="children",
                   cf=('reporting', 'max_children'), type=int,
                   default=0,
                   help='Maximum number of children for the reporting collector')]

    def __init__(self):
        """Setup the collector.  This may be called by the daemon or though
        bcfg2-admin"""
        self.terminate = None
        self.context = None
        self.children = []
        self.cleanup_threshold = 25

        self.semaphore = None
        if Bcfg2.Options.setup.children > 0:
            self.semaphore = threading.Semaphore(
                value=Bcfg2.Options.setup.children)

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
            self.logger.error("Storage backend %s failed to validate: %s" %
                              (self.storage.__class__.__name__,
                               sys.exc_info()[1]))

    def run(self):
        """Startup the processing and go!"""
        self.terminate = threading.Event()
        atexit.register(self.shutdown)
        self.context = daemon.DaemonContext(detach_process=True)
        iter = 0

        if Bcfg2.Options.setup.daemon:
            self.logger.debug("Daemonizing")
            self.context.pidfile = TimeoutPIDLockFile(
                Bcfg2.Options.setup.daemon, acquire_timeout=5)
            # Attempt to ensure lockfile is able to be created and not stale
            try:
                self.context.pidfile.acquire()
            except LockFailed:
                self.logger.error("Failed to daemonize: %s" %
                                  sys.exc_info()[1])
                self.shutdown()
                return
            except LockTimeout:
                try: # attempt to break the lock
                    os.kill(self.context.pidfile.read_pid(), 0)
                except (OSError, TypeError): # No process with locked PID
                    self.context.pidfile.break_lock()
                else:
                    self.logger.error("Failed to daemonize: "
                                      "Failed to acquire lock on %s" %
                                      Bcfg2.Options.setup.daemon)
                    self.shutdown()
                    return
            else:
                self.context.pidfile.release()

            self.context.open()
            self.logger.info("Starting daemon")

        self.transport.start_monitor(self)

        while not self.terminate.isSet():
            try:
                interaction = self.transport.fetch()
                if not interaction:
                    continue
                if self.semaphore:
                    self.semaphore.acquire()
                store_thread = ReportingStoreThread(interaction, self.storage,
                                                    semaphore=self.semaphore)
                store_thread.start()
                self.children.append(store_thread)

                iter += 1
                if iter >= self.cleanup_threshold:
                    self.reap_children()
                    iter = 0

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

    def reap_children(self):
        """Join any non-live threads"""
        newlist = []

        self.logger.debug("Starting reap_children")
        for child in self.children:
            if child.isAlive():
                newlist.append(child)
            else:
                child.join()
                self.logger.debug("Joined child thread %s" % child.getName())
        self.children = newlist
