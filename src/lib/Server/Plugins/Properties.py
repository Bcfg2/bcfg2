import copy
import lxml.etree

import Bcfg2.Server.Plugin


class PropertyFile(Bcfg2.Server.Plugin.StructFile):
    """Class for properties files."""
    pass

class PropDirectoryBacked(Bcfg2.Server.Plugin.DirectoryBacked):
    __child__ = PropertyFile


class Properties(Bcfg2.Server.Plugin.Plugin,
                 Bcfg2.Server.Plugin.Connector):
    """
       The properties plugin maps property
       files into client metadata instances.
    """
    name = 'Properties'
    version = '$Revision$'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        try:
            self.store = PropDirectoryBacked(self.data, core.fam)
        except OSError:
            e = sys.exc_info()[1]
            Bcfg2.Server.Plugin.logger.error("Error while creating Properties "
                                             "store: %s %s" % (e.strerror, e.filename))
            raise Bcfg2.Server.Plugin.PluginInitError

    def get_additional_data(self, _):
        return copy.deepcopy(self.store.entries)
