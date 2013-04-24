"""
The local transport.  Stats are pickled and written to
<repo>/store/<hostname>-timestamp

Leans on FileMonitor to detect changes
"""

import os
import select
import time
import traceback
import Bcfg2.Server.FileMonitor
from Bcfg2.Reporting.Collector import ReportingCollector, ReportingError
from Bcfg2.Reporting.Transport.base import TransportBase, TransportError
from Bcfg2.Compat import cPickle


class LocalFilesystem(TransportBase):
    def __init__(self, setup):
        super(LocalFilesystem, self).__init__(setup)

        self.work_path = "%s/work" % self.data
        self.debug_log("LocalFilesystem: work path %s" % self.work_path)
        self.fmon = None
        self._phony_collector = None

        #setup our local paths or die
        if not os.path.exists(self.work_path):
            try:
                os.makedirs(self.work_path)
            except:
                self.logger.error("%s: Unable to create storage: %s" %
                    (self.__class__.__name__,
                        traceback.format_exc().splitlines()[-1]))
                raise TransportError

    def set_debug(self, debug):
        rv = TransportBase.set_debug(self, debug)
        if self.fmon is not None:
            self.fmon.set_debug(debug)
        return rv

    def start_monitor(self, collector):
        """Start the file monitor.  Most of this comes from BaseCore"""
        setup = self.setup
        try:
            fmon = Bcfg2.Server.FileMonitor.available[setup['filemonitor']]
        except KeyError:
            self.logger.error("File monitor driver %s not available; "
                              "forcing to default" % setup['filemonitor'])
            fmon = Bcfg2.Server.FileMonitor.available['default']
        if self.debug_flag:
            self.fmon.set_debug(self.debug_flag)
        try:
            self.fmon = fmon(debug=self.debug_flag)
            self.logger.info("Using the %s file monitor" %
                             self.fmon.__class__.__name__)
        except IOError:
            msg = "Failed to instantiate file monitor %s" % \
                setup['filemonitor']
            self.logger.error(msg, exc_info=1)
            raise TransportError(msg)
        self.fmon.start()
        self.fmon.AddMonitor(self.work_path, self)

    def store(self, hostname, metadata, stats):
        """Store the file to disk"""

        try:
            payload = cPickle.dumps(dict(hostname=hostname,
                                         metadata=metadata,
                                         stats=stats))
        except:  # pylint: disable=W0702
            msg = "%s: Failed to build interaction object: %s" % \
                (self.__class__.__name__,
                 traceback.format_exc().splitlines()[-1])
            self.logger.error(msg)
            raise TransportError(msg)

        fname = "%s-%s" % (hostname, time.time())
        save_file = os.path.join(self.work_path, fname)
        tmp_file = os.path.join(self.work_path, "." + fname)
        if os.path.exists(save_file):
            self.logger.error("%s: Oops.. duplicate statistic in directory." %
                self.__class__.__name__)
            raise TransportError

        # using a tmpfile to hopefully avoid the file monitor from grabbing too
        # soon
        saved = open(tmp_file, 'wb')
        try:
            saved.write(payload)
        except IOError:
            self.logger.error("Failed to store interaction for %s: %s" %
                (hostname, traceback.format_exc().splitlines()[-1]))
            os.unlink(tmp_file)
        saved.close()
        os.rename(tmp_file, save_file)

    def fetch(self):
        """Fetch the next object"""
        event = None
        fmonfd = self.fmon.fileno()
        if self.fmon.pending():
            event = self.fmon.get_event()
        elif fmonfd:
            select.select([fmonfd], [], [], self.timeout)
            if self.fmon.pending():
                event = self.fmon.get_event()
        else:
            # pseudo.. if nothings pending sleep and loop
            time.sleep(self.timeout)

        if not event or event.filename == self.work_path:
            return None

        #deviate from the normal routines here we only want one event
        etype = event.code2str()
        self.debug_log("Recieved event %s for %s" % (etype, event.filename))
        if os.path.basename(event.filename)[0] == '.':
            return None
        if etype in ('created', 'exists'):
            self.debug_log("Handling event %s" % event.filename)
            payload = os.path.join(self.work_path, event.filename)
            try:
                payloadfd = open(payload, "rb")
                interaction = cPickle.load(payloadfd)
                payloadfd.close()
                os.unlink(payload)
                return interaction
            except IOError:
                self.logger.error("Failed to read payload: %s" %
                    traceback.format_exc().splitlines()[-1])
            except cPickle.UnpicklingError:
                self.logger.error("Failed to unpickle payload: %s" %
                    traceback.format_exc().splitlines()[-1])
                payloadfd.close()
                raise TransportError
        return None

    def shutdown(self):
        """Called at program exit"""
        if self.fmon:
            self.fmon.shutdown()
        if self._phony_collector:
            self._phony_collector.shutdown()

    def rpc(self, method, *args, **kwargs):
        """
        Here this is more of a dummy.  Rather then start a layer
        which doesn't exist or muck with files, start the collector

        This will all change when other layers are added
        """
        try:
            if not self._phony_collector:
                self._phony_collector = ReportingCollector(self.setup)
        except ReportingError:
            raise TransportError
        except:
            self.logger.error("Failed to load collector: %s" %
                traceback.format_exc().splitlines()[-1])
            raise TransportError

        if not method in self._phony_collector.storage.__class__.__rmi__ or \
                not hasattr(self._phony_collector.storage, method):
            self.logger.error("Unknown method %s called on storage engine %s" %
                (method, self._phony_collector.storage.__class__.__name__))
            raise TransportError


        try:
            cls_method = getattr(self._phony_collector.storage, method)
            return cls_method(*args, **kwargs)
        except:
            self.logger.error("RPC method %s failed: %s" %
                (method, traceback.format_exc().splitlines()[-1]))
            raise TransportError

