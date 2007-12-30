__revision__ = '$Revision$'

__all__ = ['Mode', 'Client', 'Compare', 'Fingerprint', 'Init', 'Minestruct',
           'Pull', 'Tidy', 'Viz']

import ConfigParser, lxml.etree, logging
from Bcfg2.Settings import settings

class Mode(object):
    '''Help message has not yet been added for mode'''
    __shorthelp__ = 'Shorthelp not defined yet'
    __longhelp__ = 'Longhelp not defined yet'
    __args__ = []

    def __init__(self):
        self.log = logging.getLogger('Bcfg2.Server.Admin.Mode')
        self.repo_path = settings.SERVER_REPOSITORY

    def __call__(self, args):
      return

    def errExit(self, emsg):
        print emsg
        raise SystemExit(1)
        
    def load_stats(self, client):
        stats = lxml.etree.parse("%s/etc/statistics.xml" % (self.repo_path))
        hostent = stats.xpath('//Node[@name="%s"]' % client)
        if not hostent:
            self.errExit("Could not find stats for client %s" % (client))
        return hostent[0]

