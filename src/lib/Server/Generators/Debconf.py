'''this generator handles production of client-specific debconf files'''
__revision__ = '$Revision$'

from Bcfg2.Server.Generator import Generator, DirectoryBacked
from elementtree.ElementTree import XML, Element

class Debconf(Generator):
    '''Debconf takes <data>/template.dat and adds entries for
    -> hostname
    -> video driver'''
    __name__ = 'Debconf'
    __version__ = '$Revision$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __provides__ = {'ConfigFile':{}}

    probes = [Element("probe", name='VGA', interpreter='/bin/sh', source='Debconf')]
    probes[0].text = '''
    XSERVER='/usr/bin/X11/X|/usr/X11R6/bin/X'
    if [ XFree86 -configure 2>/dev/null ] ; then
       VGACARD=`tail -50 /root/XF86Config.new | grep Driver | awk -F\" '{print $2}'`
    elif  ps auxww | egrep ${XSERVER} | grep -v grep > /dev/null ;then
       if [ -e /etc/X11/XF86Config ]; then
           VGACARD=`tail -50 /etc/X11/XF86Config | grep Driver | awk -F\" '{print $2}'`
       else
           VGACARD=`tail -50 /etc/X11/XF86Config-4 | grep Driver | awk -F\" '{print $2}'`
       fi
    else
       VGACARD=nv
    fi
    echo ${VGACARD}
    '''
    
    def __setup__(self):
        self.__provides__['ConfigFile']['/var/spool/debconf/config.dat'] = self.build_config_dat
        self.repo = DirectoryBacked(self.data, self.core.fam)
        self.xsensed = {}

    def build_config_dat(self, entry, metadata):
        '''build debconf file for client'''
        entry.attrib['owner'] = 'root'
        entry.attrib['group'] = 'root'
        entry.attrib['perms'] = '0600'
        filedata = self.repo.entries['config.dat']
        xdriver = self.xsensed.get(metadata.hostname, "nv")
        entry.text = filedata % (metadata.hostname, xdriver)

    def get_probes(self, metadata):
        '''Send out X probe'''
        return self.probes

    def accept_probe_data(self, metadata, probedata):
        if probedata.attrib['name'] == "VGA":
            self.xsensed[metadata.hostname] = probedata.text
            
    

    
