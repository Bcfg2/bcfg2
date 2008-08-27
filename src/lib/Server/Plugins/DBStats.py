import Bcfg2.Server.Plugin
import Bcfg2.Server.Reports.importscript
from Bcfg2.Server.Reports.reports.models import Client, Entries
import difflib, lxml.etree, time, logging, datetime
import Bcfg2.Server.Reports.settings

from Bcfg2.Server.Reports.updatefix import update_database
import traceback
# for debugging output only
logger = logging.getLogger('Bcfg2.Plugins.DBStats')

class DBStats(Bcfg2.Server.Plugin.StatisticsPlugin):
    __name__ = 'DBStats'
    __version__ = '$Id$'
        
    def __init__(self, core, datastore):
        self.cpath = "%s/Metadata/clients.xml" % datastore
        self.core = core
        logger.debug("Searching for new models to add to the statistics database")
        try:
            update_database()
        except Exception, inst:
            logger.debug(str(inst))
            logger.debug(str(type(inst)))

    def StoreStatistics(self, mdata, xdata):
        newstats = xdata.find("Statistics")
        newstats.set('time', time.asctime(time.localtime()))
        e = lxml.etree.Element('Node', name=mdata.hostname)
        e.append(newstats)
        container = lxml.etree.Element("ConfigStatistics")
        container.append(e)
        
        # FIXME need to build a metadata interface to expose a list of clients
        # FIXME Server processing the request should be mentionned here
        start = time.time()
        Bcfg2.Server.Reports.importscript.load_stats(
            self.core.metadata.clientdata, container, 0, True)
        logger.info("Imported data in the reason fast path in %s second" % (time.time() - start))

    def GetExtra(self, client):
        c_inst = Client.objects.filter(name=client)[0]
        return [(a.entry.kind, a.entry.name) for a in
                c_inst.current_interaction.extra()]

    def GetCurrentEntry(self, client, e_type, e_name):
        c_inst = Client.objects.filter(name=client)[0]
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
                
        if entry.reason.current_diff != '':
            ret.append('\n'.join(difflib.restore(\
                entry.reason.current_diff.split('\n'), 1)))
        else:
            ret.append(None)
        return ret
