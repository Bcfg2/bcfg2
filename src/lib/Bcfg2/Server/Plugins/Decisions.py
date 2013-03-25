""" The Decisions plugin provides a flexible method to whitelist or
blacklist certain entries. """

import os
import lxml.etree
import Bcfg2.Server.Plugin


class DecisionFile(Bcfg2.Server.Plugin.SpecificData):
    """ Representation of a Decisions XML file """

    def __init__(self, name, specific, encoding):
        Bcfg2.Server.Plugin.SpecificData.__init__(self, name, specific,
                                                  encoding)
        self.contents = None

    def handle_event(self, event):
        Bcfg2.Server.Plugin.SpecificData.handle_event(self, event)
        self.contents = lxml.etree.XML(self.data)

    def get_decisions(self):
        """ Get a list of whitelist or blacklist tuples """
        return [(x.get('type'), x.get('name'))
                for x in self.contents.xpath('.//Decision')]


class Decisions(Bcfg2.Server.Plugin.EntrySet,
                Bcfg2.Server.Plugin.Plugin,
                Bcfg2.Server.Plugin.Decision):
    """ Decisions plugin

    Arguments:
    - `core`: Bcfg2.Core instance
    - `datastore`: File repository location
    """
    basename_is_regex = True
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Decision.__init__(self)
        Bcfg2.Server.Plugin.EntrySet.__init__(self, '(white|black)list',
                                              self.data, DecisionFile,
                                              core.setup['encoding'])
        core.fam.AddMonitor(self.data, self)

    def HandleEvent(self, event):
        """ Handle events on Decision files by passing them off to
        EntrySet.handle_event """
        if event.filename != self.path:
            return self.handle_event(event)

    def GetDecisions(self, metadata, mode):
        ret = []
        for cdt in self.get_matching(metadata):
            if os.path.basename(cdt.name).startswith(mode):
                ret.extend(cdt.get_decisions())
        return ret
