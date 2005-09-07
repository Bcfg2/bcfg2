'''
#-------------------------------------------
# Script Name: vhost.py 
# Script Version: 1.0
# Date: 20 July 2005
# Author: Scott R Behrens
# Description: opens a request file, genereates a vhost httpd.conf file, and establishes symlinks
# Revision History:
#    1.0/<20-7-2005>: orignal version
#    1.1/<20-7-2005>: now genreates multiple files based on XML document 
#    1.2/<20-8-2005>: generates one file encoded in base64
#    1.3/<06-9-2005>: cleanup some pylint and style problems
#-------------------------------------------
'''
__revision__ = '$Revision$'

from copy import deepcopy
from elementtree.ElementTree import XML, Element, SubElement
from Bcfg2.Server.Generator import SingleXMLFileBacked
from Bcfg2.Server.Plugin import Plugin

# Global Variables for paths of apache
sitesen = "/etc/apache2/sites-enabled/"
sitesav = "/etc/apache2/sites-available/"

class VhostFile(SingleXMLFileBacked):
    '''The Vhost file contains webserver vhost configuration elements'''

    def Index(self):
        self.meta = XML(self.data)

    def BuildStructures(self, metadata):
        '''Build apache+vhost bundle'''
        output = Element("Bundle", name='apache-vhost', version='2.0')
        self.serverlist = []
        for server in self.meta.findall("server"):
            self.serverlist.append(server.attrib['name'])
            if server.attrib['name'] in metadata.hostname:
                for vhost in server.findall("vhost"):
                    name = vhost.get('name')
                    SubElement(output, "SymLink", name=sitesen+name, to=sitesav+name)
                    SubElement(output, "ConfigFile", name="/etc/apache2/sites-available/" + name)
                    SubElement(output, "ConfigFile", name='/etc/default/apache2')
                    if [software for software in self.meta.findall('Software') if metadata.hostname in self.serverlist]:
                        for child in software.getchildren():
                            output.append(deepcopy(child))
        return [output]

class Vhost(Plugin):
    '''This Structure is good for the pile of independent configs needed for most actual systems'''
    __name__ =  'Vhost'
    __version__ = '$Id$'
    __author__ = 'behrens@mcs.anl.gov'

    '''Vhost creates independent clauses based on client metadata'''
    def __init__(self, core, datastore):
        Plugin.__init__(self, core, datastore)
        self.Vhost = VhostFile("%s/Vhost/Vhost.xml"%(datastore), self.core.fam)
        self.BuildStructures = self.Vhost.BuildStructures
