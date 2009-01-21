import Bcfg2.Server.Plugin, lxml.etree

class DecisionFile(Bcfg2.Server.Plugin.SpecificData):
    def handle_event(self, event):
        Bcfg2.Server.Plugin.SpecificData.handle_event(self, event)
        self.contents = lxml.etree.XML(self.data)

    def get_decisions(self):
        return [(x.get('type'), x.get('name')) for x in self.contents.xpath('.//Decision')]

class DecisionSet(Bcfg2.Server.Plugin.EntrySet):
    def __init__(self, path, fam, encoding):
        """Container for decision specification files
        
        Arguments:
        - `path`: repository path
        - `fam`: reference to the file monitor
        - `encoding`: XML character encoding
        """
        pattern = '(white|black)list'
        Bcfg2.Server.Plugin.EntrySet.__init__(self, pattern, path, \
                                              DecisionFile, encoding)
        fam.AddMonitor(path, self)

    def HandleEvent(self, event):
        if event.filename != self.path:
            return self.handle_event(event)

    def GetDecisions(self, metadata, mode):
        ret = []
        candidates = [c for c in self.get_matching(metadata)
                      if c.name.split('/')[-1].startswith(mode)]
        for c in candidates:
            ret += c.get_decisions()
        return ret

class Decisions(Bcfg2.Server.Plugin.Plugin,
                Bcfg2.Server.Plugin.Decision,
                DecisionSet):
    name = 'Decisions'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        """Decisions plugins
        
        Arguments:
        - `core`: Bcfg2.Core instance
        - `datastore`: File repository location
        """
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Decision.__init__(self)
        DecisionSet.__init__(self, self.data, core.fam, core.encoding)
    
