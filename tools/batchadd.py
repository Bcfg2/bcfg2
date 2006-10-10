#!/usr/bin/python

import sys, os
from datetime import date
os.environ['DJANGO_SETTINGS_MODULE'] = 'Hostbase.settings'
from Hostbase.hostbase.models import *
from Hostbase.settings import DEFAULT_MX, PRIORITY

host_attribs = ['hostname', 'whatami', 'netgroup', 'security_class', 'support',
                'csi', 'printq', 'dhcp', 'outbound_smtp', 'primary_user',
                'administrator', 'location', 'expiration_date', 'comments']

def checkformat(values):
    filelist = []
    for pair in values:
        filelist.append(pair[0])

    lines = len(filelist)

    while True:
        if filelist and not filelist[0:14] == host_attribs:
            # figure out what to do here
            return 0
            sys.exit()
        elif not filelist:
            return 1
        else:
            filelist = filelist[14:]
            while True:
                if filelist and filelist[0] == 'mac_addr':
                    filelist.pop(0)
                if filelist and filelist[0] == 'hdwr_type':
                    filelist.pop(0)
                while filelist and filelist[0] == 'ip_addr':
                    filelist.pop(0)
                while filelist and filelist[0] == 'cname':
                    filelist.pop(0)

                if (filelist and filelist[0] == 'hostname') or not filelist:
                    break

# argument handling for batchadd
try:
    fd = open(sys.argv[1], 'r')
except (IndexError, IOError):
    print "\nUsage: batchadd.py filename\n"
    sys.exit()

lines = fd.readlines()
info = []
for line in lines:
    if not line.lstrip(' ')[0] == '#' and not line == '\n':
        info.append(line.split("->"))
    
for x in range(0,len(info)):
    if len(info[x]) > 1:
        info[x][0] = info[x][0].strip()
        info[x][1] = info[x][1].strip()
    else:
        print "Error: file format"

if info[0][0] == 'mx' and info[1][0] == 'priority':
    mx, created = MX.objects.get_or_create(mx=info[0][1], priority=info[1][1])
    try:
        info.pop(0)
        info.pop(0)
    except:
        print "Error: file format"
        sys.exit()
else:
    mx, created = MX.objects.get_or_create(mx=DEFAULT_MX, priority=PRIORITY)
if created:
    mx.save()

if not checkformat(info):
    print "Error: file format"
    sys.exit()

while True:
    blank = Host()
    for attrib in host_attribs:
        try:
            pair = info.pop(0)
        except:
            sys.exit()
        if pair[0] == 'dhcp' or pair[0] == 'outbound_smtp':
            if pair[1] == 'y':
                blank.__dict__[pair[0]] = 1
            else:
                blank.__dict__[pair[0]] = 0
        elif pair[0] == 'expiration_date':
            (year, month, day) = pair[1].split("-")
            blank.expiration_date = date(int(year), int(month), int(day))
        elif pair[0] in host_attribs:
            blank.__dict__[pair[0]] = pair[1]

    try:
        host = Host.objects.get(hostname=blank.hostname)
        print "Error: %s already exists in hostbase" % blank.hostname
        sys.exit()
    except:
        pass
        # do something here
    blank.status = 'active'
    blank.save()
    newhostname = blank.hostname.split(".")[0]
    newdomain = blank.hostname.split(".", 1)[1]
    while True:
        try:
            info[0]
        except:
            sys.exit()
        if info[0][0] == 'mac_addr':
            pair = info.pop(0)
            try:
                Interface.get(mac_addr=pair[1])
                print "Error: %s already exists" % inter.mac_addr
                sys.exit()
            except:
                inter = Interface.objects.create(host=blank, mac_addr=pair[1], hdwr_type='eth')
                inter.save()
        elif info[0][0] == 'hdwr_type':
            pair = info.pop(0)
            inter.hdwr_type = pair[1]
            inter.save()
        elif info[0][0] == 'ip_addr':
            pair = info.pop(0)
            ip = IP.objects.create(interface=inter, ip_addr=pair[1], num=1)
            hostnamenode = Name(ip=ip, name=blank.hostname, dns_view='global', only=False)
            hostnamenode.save()
            namenode = Name(ip=ip, name=".".join([newhostname + "-" + inter.hdwr_type,
                                                      newdomain]),
                            dns_view="global", only=False)
            namenode.save()
            subnetnode = Name(ip=ip, name=newhostname + "-" + 
                              ip.ip_addr.split(".")[2] + "." +
                              newdomain, dns_view="global", only=False)
            subnetnode.save()
            hostnamenode.mxs.add(mx)
            namenode.mxs.add(mx)
            subnetnode.mxs.add(mx)
        elif info[0][0] == 'cname':
            pair = info.pop(0)
            cname = CName.objects.create(name=hostnamenode, cname=pair[1])
            cname.save()
        else:
            break

