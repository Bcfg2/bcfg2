#!/usr/bin/python
import os
from getopt import getopt, GetoptError
from re import split
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'Hostbase.settings'
from Hostbase.hostbase.models import Host

attribs = ['administrator',
           'comments',
           'csi',
           'dhcp',
           'expiration_date',
           'hostname',
           'last',
           'location',
           'netgroup',
           'outbound_smtp',
           'primary_user',
           'printq',
           'security_class',
           'support',
           'status',
           'whatami']

already_exists = None
#here's my attempt at making the command line idiot proof
#you must supply and arugument and hostname for hostbase.py to run
try:
    (opts, args) = getopt(sys.argv[1:], 'l:c:')
    sys.argv[1]
    if len(split("\.", opts[0][1])) == 1:
        hosttouse = opts[0][1] + ".mcs.anl.gov"
    else:
        hosttouse = opts[0][1]
except (GetoptError, IndexError):
    print("\nUsage: hostbase.py -flag (hostname)\n")
    print("Flags:")
    print("\t-l   look (hostname)\n")
#    print("\t-c   copy (hostname)\n")
    sys.exit()

try:
    host = Host.objects.get(hostname=hosttouse)
except:
    print("Error: host %s not in hostbase" % hosttouse)
    sys.exit(1)
interfaces = []
for interface in host.interface_set.all():
    interfaces.append([interface, interface.ip_set.all()])
hostinfo = "\n"
for attrib in attribs:
    if not (opts[0][0] == '-c' and attrib in ['status', 'last']):
        if attrib == 'dhcp' or attrib == 'outbound_smtp':
            if host.__dict__[attrib]:
                hostinfo += "%-32s-> %s\n" % (attrib, 'y')
            else:
                hostinfo += "%-32s-> %s\n" % (attrib, 'n')
        else:
            hostinfo += "%-32s-> %s\n" % (attrib, host.__dict__[attrib])
for interface in interfaces:
    hostinfo += "\n%-32s-> %s\n" % ('mac_addr', interface[0].mac_addr)
    hostinfo += "%-32s-> %s\n" % ('hdwr_type', interface[0].hdwr_type)
    for ip in interface[1]:
        hostinfo += "%-32s-> %s\n" % ('ip_addr', ip.ip_addr)

if opts[0][0] == '-l':
    """Displays general host information"""
    print(hostinfo)

if opts[0][0] == '-c':
    """Provides pre-filled template to copy a host record"""
    fd = open('/tmp/hostbase.%s.tmp' % host.id, 'w')
    fd.write(hostinfo)
    fd.close()
    os.system('vi + /tmp/hostbase.%s.tmp' % host.id)
    os.system('batchadd.py /tmp/hostbase.%s.tmp' % host.id)
    os.system('rm /tmp/hostbase.%s.tmp' % host.id)
