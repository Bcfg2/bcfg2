#!/usr/bin/python

import lxml.etree, sys, ConfigParser

#this will be replaced by redeadin config file, but I am in a hurry right now
CP = ConfigParser.ConfigParser()
CP.read(['/etc/bcfg2.conf'])
try:
    prefix = CP.get('server', 'repository')
except:
    prefix = "/disks/bcfg2"

if len(sys.argv) < 2:
    print "Usage client-query.py -d|u|p <profile name>"
    print "\t -d\t\t shows the clients that are currently down"
    print "\t -u\t\t shows the clients that are currently up"
    print "\t -p <profile name>\t shows all the clients of that profile"
    sys.exit(1)

xml = lxml.etree.parse('%s/Metadata/clients.xml'%prefix)
for client in xml.findall('.//Client'):
    if '-u' in sys.argv:
        if client.get("pingable") == "Y":
            print client.get("name")
    elif '-d' in sys.argv:
        if client.get("pingable") == "N":
            print client.get("name")
    elif '-p' in sys.argv and sys.argv[sys.argv.index('-p') + 1] != '':
        if client.get("profile") == sys.argv[sys.argv.index('-p') + 1]:
            print client.get("name")
    elif '-a' in sys.argv:
        print client.get("name")


        


                                                                                               
