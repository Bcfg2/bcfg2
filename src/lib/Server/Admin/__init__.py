__revision__ = '$Revision$'

__all__ = ['Mode', 'Client', 'Compare', 'Init', 'Minestruct',
           'Pull', 'Query', 'Snapshots', 'Tidy', 'Viz']

import ConfigParser
import logging
import lxml.etree
import sys

import Bcfg2.Server.Core
import Bcfg2.Options

class ModeOperationError(Exception):
    pass

class Mode(object):
    '''Help message has not yet been added for mode'''
    __shorthelp__ = 'Shorthelp not defined yet'
    __longhelp__ = 'Longhelp not defined yet'
    __args__ = []
    def __init__(self, configfile):
        self.configfile = configfile
        self.__cfp = False
        self.log = logging.getLogger('Bcfg2.Server.Admin.Mode')

    def getCFP(self):
        if not self.__cfp:
            self.__cfp = ConfigParser.ConfigParser()
            self.__cfp.read(self.configfile)
        return self.__cfp

    cfp = property(getCFP)

    def __call__(self, args):
        if len(args) > 0 and args[0] == 'help':
            print self.__longhelp__
            raise SystemExit(0)

    def errExit(self, emsg):
        print emsg
        raise SystemExit(1)
        
    def get_repo_path(self):
        '''return repository path'''
        return self.cfp.get('server', 'repository')

    def load_stats(self, client):
        stats = lxml.etree.parse("%s/etc/statistics.xml" %
                                (self.get_repo_path()))
        hostent = stats.xpath('//Node[@name="%s"]' % client)
        if not hostent:
            self.errExit("Could not find stats for client %s" % (client))
        return hostent[0]

class MetadataCore(Mode):
    '''Base class for admin-modes that handle metadata'''
    def __init__(self, configfile, usage):
        Mode.__init__(self, configfile)
        options = {'plugins': Bcfg2.Options.SERVER_PLUGINS}
        setup = Bcfg2.Options.OptionParser(options)
        setup.hm = usage
        setup.parse(sys.argv[1:])
        try:
            self.bcore = Bcfg2.Server.Core.Core(self.get_repo_path(),
                                                setup['plugins'],
                                                'foo', 'UTF-8')
        except Bcfg2.Server.Core.CoreInitError, msg:
            self.errExit("Core load failed because %s" % msg)
        self.bcore.fam.handle_events_in_interval(5)
        self.metadata = self.bcore.metadata

class StructureMode(MetadataCore):
    pass
