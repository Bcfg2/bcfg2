""" The Decisions plugin provides a flexible method to whitelist or
blacklist certain entries. """

import os
import Bcfg2.Server.Plugin
import Bcfg2.Server.FileMonitor


class DecisionFile(Bcfg2.Server.Plugin.StructFile):
    """ Representation of a Decisions XML file """

    def get_decisions(self, metadata):
        """ Get a list of whitelist or blacklist tuples """
        if self.xdata is None:
            # no white/blacklist has been read yet, probably because
            # it doesn't exist
            return []
        return [(x.get('type'), x.get('name'))
                for x in self.XMLMatch(metadata).xpath('.//Decision')]


class Decisions(Bcfg2.Server.Plugin.Plugin,
                Bcfg2.Server.Plugin.Decision):
    """ Decisions plugin """
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core)
        Bcfg2.Server.Plugin.Decision.__init__(self)
        self.whitelist = DecisionFile(os.path.join(self.data, "whitelist.xml"))
        self.blacklist = DecisionFile(os.path.join(self.data, "blacklist.xml"))

    def GetDecisions(self, metadata, mode):
        return getattr(self, mode).get_decisions(metadata)
