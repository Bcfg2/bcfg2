__revision__ = '$Revision$'

__all__ = ['Mode', 'Client', 'Compare', 'Fingerprint', 'Init', 'Minestruct',
           'Pull', 'Query', 'Reports', 'Tidy', 'Viz']

import ConfigParser, lxml.etree, logging

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
        stats = lxml.etree.parse("%s/etc/statistics.xml" % (self.get_repo_path()))
        hostent = stats.xpath('//Node[@name="%s"]' % client)
        if not hostent:
            self.errExit("Could not find stats for client %s" % (client))
        return hostent[0]

