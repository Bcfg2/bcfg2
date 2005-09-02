#!/usr/bin/python
#-------------------------------------------
# Script Name: vhost.py 
# Script Version: 1.0
# Date: 20 July 2005
# Author: Scott R Behrens
# Description: opens a request file, genereates a vhost httpd.conf file, and establishes symlinks
# Revision History:
#    1.0/<20-7-2005>: orignal version
#    1.1/<20-7-2005>: now genreates multiple files based on XML document 
#    1.2/<20-14-2005>: generates one file encoded in base64
#-------------------------------------------

import sys, re, os
from getopt import getopt, GetoptError
from elementtree.ElementTree import XML, Element
from Bcfg2.Server.Generator import SingleXMLFileBacked
from Bcfg2.Server.Structure import Structure


# Global Variables for paths of apache
sitesen = "/etc/apache2/sites-enabled/"
sitesav = "/etc/apache2/sites-available/"

class VhostFile(SingleXMLFileBacked):
    '''The Base file contains unstructured/independent configuration elements'''

    def Index(self):
    	self.meta = XML(self.data)

    def Construct(self, metadata):
	self.output = Element("Bundle", name='apache-vhost', version='2.0')
	self.serverlist = []
        for server in self.meta.findall("server"):
	    self.serverlist.append(server.attrib['name'])
            if server.attrib['name'] in metadata.hostname:
                for vhost in server.findall("vhost"):
                    name = vhost.get('name')
                    email = vhost.get('email')
                    root = vhost.get('root')
                    opt = vhost.get('opt')
                    self.output.append(XML("<SymLink name=\'" + sitesen + name + "\' to=\'" + sitesav + name + "\'/>"))
                    self.output.append(XML("<ConfigFile name=\'/etc/apache2/sites-available/" + name + "\' encode=\'base64\'/>"))
                    self.output.append(XML("<ConfigFile name=\'/etc/default/apache2\'/>"))
	if [software for software in self.meta.findall('Software') if metadata.hostname in self.serverlist]:
	    for child in software.getchildren():
	        self.output.append(child)
        return [self.output]

class Vhost(Structure):
    '''This Structure is good for the pile of independent configs needed for most actual systems'''
    __name__ =  'Vhost'
    __version__ = '$Id: s.Vhost.py 1.15 04/12/03 10:23:33-06:00 desai@topaz.mcs.anl.gov $'

    '''Vhost creates independent clauses based on client metadata'''
    def __init__(self, core, datastore):
        Structure.__init__(self, core, datastore)
        self.Vhost = VhostFile("%s/Vhost/Vhost.xml"%(datastore), self.core.fam)
        self.Construct = self.Vhost.Construct
