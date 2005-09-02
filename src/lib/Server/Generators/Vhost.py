'''This module manages vhost files for bcfg2'''
__revision__ = '$Revision: $'
#-------------------------------------------
# Script Name: vhost.py 
# Script Version: 1.0
# Date: 20 July 2005
# Author: Scott R Behrens
# Description: opens a request file, genereates a vhost httpd.conf file, and establishes symlinks
# Revision History:
#    1.0/<20-7-2005>: orignal version
#    1.1/<20-7-2005>: now genreates multiple files based on XML document 
#    1.2/<24-7-2005>: generates one file encoded in base64
#    1.3/<02-8-2005>: almost a functional generator
#-------------------------------------------

import sys, re, os
import base64
from getopt import getopt, GetoptError
from socket import gethostbyname
from Bcfg2.Server.Generator import SingleXMLFileBacked
from elementtree.ElementTree import XML, ElementTree
from Bcfg2.Server.Generator import Generator, DirectoryBacked

##############################################
# 
##############################################
class VhostFile(SingleXMLFileBacked):
    '''The Base file contains unstructured/independent configuration elements'''
    sitesen = "/etc/apache2/sites-enabled/"
    sitesav = "/etc/apache2/sites-available/"

    def __init__(self, name, fam):
        self.dispatch = {}
        SingleXMLFileBacked.__init__(self, name, fam) 

    def Index(self):
        self.store = XML(self.data)
        # this isnt file backed yet
        self.http = open('/disks/bcfg2/Vhost/default.httpd', 'r').readlines()
        for server in self.store.findall("server"):
            for vhost in server.findall("vhost"):
                name = vhost.get('name')
                self.dispatch[self.sitesav + name] = self.generateconf 		
 	self.dispatch['/etc/default/apache2'] = self.generateservice
    
    def generateservice(self, entry, metadata):
	if [x for x in self.store.findall('server') if x.get('name') == metadata.hostname]:
	    entry.text='NO_START=0\n'
        else:
	    entry.text='NO_START=1\n'
	entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0644'})
		
    def defaultgenerate(self, entry, metadata):
	if [x for x in self.store.findall('server') if x.get('name') == metadata.hostname]:
	    entry.set('status', 'on')
        else:
	    entry.set('status', 'off')
 		

    def generateconf(self, entry, metadata):
	if [server for server in self.store.findall('server') if server.get('name') == metadata.hostname]:
	    if [vhost for vhost in server.findall('vhost') if self.sitesav + vhost.get('name') == entry.get('name')]:
                name = vhost.attrib['name']
                email = vhost.attrib['email']
                root = vhost.attrib['root']
                opt = vhost.attrib['opt']

        if root == "Hostname":
            choice = name
        elif root == "Ip":
            choice = gethostbyname(name) 

        config = ""
        for line in self.http:
            line = line.replace("XXemailXX", email)
            line = line.replace("XXdomainXX", name)
            line = line.replace("XXchoiceXX", choice)
            config+=line
        entry.text = base64.encodestring(config)
        entry.attrib['encoding'] = 'base64'
	entry.attrib.update({'owner':'root', 'group':'root', 'perms':'0644'})

class Vhost(Generator):
    '''This Generates the sites enabled stuff for things'''

    __name__ = 'Vhost'
    __version__ = '$Id: s.Vhost.py 1.48 05/05/13 13:13:57-05:00 behrens@mcs.anl.gov $'
    __author__ = 'bcfg-dev@mcs.anl.gov'


    def __init__(self, core, datastore):

        Generator.__init__(self, core, datastore)
        self.Vhost = VhostFile("%s/Vhost/Vhost.xml"%(datastore), self.core.fam)
        self.repository = DirectoryBacked(self.data, self.core.fam)
	self.__provides__['ConfigFile'] = self.Vhost.dispatch
	self.__provides__['Service'] = {'apache2': self.Vhost.defaultgenerate} 
