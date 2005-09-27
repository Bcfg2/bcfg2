#!/usr/bin/env python

'''This script updates to fully qualified hostnames for 0.6.11'''
__revision__ = '$Revision:$'

from ConfigParser import ConfigParser
from elementtree.ElementTree import XML, tostring
from socket import gethostbyname
from sys import argv
from glob import glob
from os import system

if __name__ == '__main__':
    hostcache = {}
    if len(argv) > 1:
        domainlist = argv[-1].split(':')
    else:
        domainlist = ['mcs.anl.gov']
    cf = ConfigParser()
    cf.read(['/etc/bcfg2.conf'])
    metadata = XML(open(cf.get('server', 'metadata') + '/metadata.xml').read())
    for client in metadata.findall('.//Client'):
        if client.get('name').count('.') == 0:
            for dom in domainlist:
                print "resolving name %s.%s..." % (client.get('name'), dom),
                try:
                    hostinfo = gethostbyname(client.get('name') + '.' + dom)
                    hostcache[client.get('name')] = dom
                    client.set('name', "%s.%s" % (client.get('name'), dom))
                    print ""
                    break
                except:
                    print "FAILED"
                    continue
                print hostinfo

    open(cf.get('server', 'metadata') + '/metadata.xml.new'), 'w').write(tostring(metadata))

    sshdir = cf.get('server', 'repository') + '/SSHbase/'
    for key in glob(sshdir + "*key.H_*"):
        hostname = key.split('.H_')[1]
        if not hostcache.has_key(hostname):
            for dom in domainlist:
                try:
                    hostinfo = gethostbyname(hostname + '.' + dom)
                    hostcache[hostname] = dom
                    break
                except:
                    continue
        if hostcache.has_key(hostname):
            system("mv %s %s.%s" % (key, key, hostcache[hostname]))
