import difflib
import logging
import lxml.etree
import platform
import sys
import time

try:
    from django.core.exceptions import MultipleObjectsReturned
except ImportError:
    pass

import Bcfg2.Server.Plugin
from Bcfg2.Server.Reports.importscript import load_stat
from Bcfg2.Server.Reports.reports.models import Client
from Bcfg2.Compat import b64decode

# for debugging output only
logger = logging.getLogger('Bcfg2.Plugins.DBStats')


class DBStats(Bcfg2.Server.Plugin.ThreadedStatistics,
              Bcfg2.Server.Plugin.PullSource):
    name = 'DBStats'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.ThreadedStatistics.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.PullSource.__init__(self)
        self.cpath = "%s/Metadata/clients.xml" % datastore
        self.core = core
        if not self.core.database_available:
            raise Bcfg2.Server.Plugin.PluginInitError

    def handle_statistic(self, metadata, data):
        newstats = data.find("Statistics")
        newstats.set('time', time.asctime(time.localtime()))

        start = time.time()
        for i in [1, 2, 3]:
            try:
                load_stat(metadata,
                          newstats,
                          self.core.encoding,
                          0,
                          logger,
                          True,
                          platform.node())
                logger.info("Imported data for %s in %s seconds" \
                            % (metadata.hostname, time.time() - start))
                return
            except MultipleObjectsReturned:
                e = sys.exc_info()[1]
                logger.error("DBStats: MultipleObjectsReturned while "
                             "handling %s: %s" % (metadata.hostname, e))
                logger.error("DBStats: Data is inconsistent")
                break
            except:
                logger.error("DBStats: Failed to write to db (lock); retrying",
                             exc_info=1)
        logger.error("DBStats: Retry limit failed for %s; aborting operation" \
                    % metadata.hostname)

    def GetExtra(self, client):
        c_inst = Client.objects.filter(name=client)[0]
        return [(a.entry.kind, a.entry.name) for a in
                c_inst.current_interaction.extra()]

    def GetCurrentEntry(self, client, e_type, e_name):
        try:
            c_inst = Client.objects.filter(name=client)[0]
        except IndexError:
            self.logger.error("Unknown client: %s" % client)
            raise Bcfg2.Server.Plugin.PluginExecutionError
        result = c_inst.current_interaction.bad().filter(entry__kind=e_type,
                                                         entry__name=e_name)
        if not result:
            raise Bcfg2.Server.Plugin.PluginExecutionError
        entry = result[0]
        ret = []
        data = ('owner', 'group', 'perms')
        for t in data:
            if getattr(entry.reason, "current_%s" % t) == '':
                ret.append(getattr(entry.reason, t))
            else:
                ret.append(getattr(entry.reason, "current_%s" % t))
        if entry.reason.is_sensitive:
            raise Bcfg2.Server.Plugin.PluginExecutionError
        elif len(entry.reason.unpruned) != 0:
            ret.append('\n'.join(entry.reason.unpruned))
        elif entry.reason.current_diff != '':
            if entry.reason.is_binary:
                ret.append(b64decode(entry.reason.current_diff))
            else:
                ret.append('\n'.join(difflib.restore(\
                    entry.reason.current_diff.split('\n'), 1)))
        elif entry.reason.is_binary:
            # If len is zero the object was too large to store
            raise Bcfg2.Server.Plugin.PluginExecutionError
        else:
            ret.append(None)
        return ret
