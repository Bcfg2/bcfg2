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

import base64
from copy import deepcopy
from elementtree.ElementTree import XML, Element, SubElement
from socket import gethostbyname
from Bcfg2.Server.Generator import SingleXMLFileBacked
from Bcfg2.Server.Plugin import Plugin, PluginExecutionError

class VhostFile(SingleXMLFileBacked):
    '''The Vhost file contains webserver vhost configuration elements'''
    sitesen = "/etc/apache2/sites-enabled/"
    sitesav = "/etc/apache2/sites-available/"

    def __init__(self, name, fam):
        self.dispatch = {'ConfigFile':{'/etc/default/apache2':self.generateApacheDefault},
                         'Service':{'apache2':self.generateApacheSvc}}
        SingleXMLFileBacked.__init__(self, name, fam)
        self.http = open('/disks/bcfg2/Vhost/default.httpd', 'r').readlines()
        self.servers = []
        self.vhosts = {}

    def Index(self):
        self.meta = XML(self.data)
        self.servers = [serv.get('name') for serv in self.meta.findall('server')]
        self.vhosts = {}
        for server in self.meta.findall("server"):
            for vhost in server.findall("vhost"):
                name = vhost.get('name')
                self.dispatch[self.sitesav + name] = self.generateSiteFile
                self.vhosts[name] = vhost

    def BuildStructures(self, metadata):
        '''Build apache+vhost bundle'''
        if metadata.hostname not in self.servers:
            return []
        output = Element("Bundle", name='apache-vhost', version='2.0')
        for server in self.meta.findall("server"):
            if server.attrib['name'] in metadata.hostname:
                for vhost in server.findall("vhost"):
                    name = vhost.get('name')
                    SubElement(output, "SymLink", name=self.sitesen+name, to=self.sitesav+name)
                    SubElement(output, "ConfigFile", name="/etc/apache2/sites-available/" + name)
                    SubElement(output, "ConfigFile", name='/etc/default/apache2')
                    for software in self.meta.findall("Software"):
                        for child in software.getchildren():
                            output.append(deepcopy(child))
        return [output]

    def generateApacheDefault(self, entry, metadata):
        '''Build /etc/default/apache2'''
        if metadata.hostname in self.servers:
            entry.text = 'NO_START=0\n'
        else:
            entry.text = 'NO_START=1\n'
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0644'})
		
    def generateApacheSvc(self, entry, metadata):
        '''Enable apache service on webservices, disable on others'''
        if metadata.hostname in self.servers:
            entry.set('status', 'on')
        else:
            entry.set('status', 'off')

    def generateSiteFile(self, entry, metadata):
        '''Build site-specific config file for vhost'''
        if metadata.hostname not in self.servers:
            raise PluginExecutionError
        vhostname = entry.get('name')[len(self.sitesav):]
        if not self.vhosts.has_key(vhostname):
            raise PluginExecutionError

        if self.vhosts[vhostname].get('root') == "Hostname":
            choice = vhostname
        else:
            choice = gethostbyname(vhostname) 

        config = ""
        for line in self.http:
            line = line.replace("XXemailXX", self.vhosts[vhostname].get('email'))
            line = line.replace("XXdomainXX", vhostname)
            line = line.replace("XXchoiceXX", choice)
            config += line
        entry.text = base64.encodestring(config)
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0644', 'encoding':'base64'})

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
        self.Entries = self.Vhost.dispatch
