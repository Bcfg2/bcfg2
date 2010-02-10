import copy
import lxml.etree

import Bcfg2.Server.Plugin


class PropertyFile(Bcfg2.Server.Plugin.XMLFileBacked):
    '''Class for properties files'''

    def Index(self):
        '''Build data into an xml object'''
        try:
            self.data = lxml.etree.XML(self.data)
        except lxml.etree.XMLSyntaxError:
            Bcfg2.Server.Plugin.logger.error("Failed to parse %s" % self.name)


class PropDirectoryBacked(Bcfg2.Server.Plugin.DirectoryBacked):
    __child__ = PropertyFile


class Properties(Bcfg2.Server.Plugin.Plugin,
                 Bcfg2.Server.Plugin.Connector):
    '''
       The properties plugin maps property
       files into client metadata instances
    '''
    name = 'Properties'
    version = '$Revision$'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.store = PropDirectoryBacked(self.data, core.fam)

    def get_additional_data(self, _):
        return copy.deepcopy(self.store.entries)
