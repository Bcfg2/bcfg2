'''this generator handles production of client-specific debconf files'''
__revision__ = '$Revision$'

from Bcfg2.Server.Generator import Generator, DirectoryBacked
from elementtree.ElementTree import XML

class Debconf(Generator):
    '''Debconf takes <data>/template.dat and adds entries for
    -> hostname
    -> video driver'''
    __name__ = 'Debconf'
    __version__ = '$Revision$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __provides__ = {'ConfigFile':{}}

    probes = [XML('''<probe interpreter='/bin/sh'>lspci|grep VGA</probe>''')]

    def __setup__(self):
        self.repo = DirectoryBacked(self.data, self.core.fam)
        self.xsensed = {}

    def build_config_dat(self, entry, metadata):
        '''build debconf file for client'''
        entry.attrib['owner'] = 'root'
        entry.attrib['group'] = 'root'
        entry.attrib['perms'] = '0600'
        filedata = self.repo.entries['config.dat']
        xdriver = self.xsensed.get(metadata.hostname, "vesa")
        entry.text = filedata % (metadata.hostname, xdriver)

    def get_probes(self, metadata):
        return self.probes

    

    
