#!/usr/bin/python

import sys, os
from datetime import date
os.environ['DJANGO_SETTINGS_MODULE'] = 'Hostbase.settings'
from Hostbase.hostbase.models import *
from Hostbase.settings import DEFAULT_MX, PRIORITY
import Hostbase.regex

host_attribs = ['hostname', 'whatami', 'netgroup', 'security_class', 'support',
                'csi', 'printq', 'dhcp', 'outbound_smtp', 'primary_user',
                'administrator', 'location', 'expiration_date', 'comments']

def handle_error(field):
    if '-f' in sys.argv:
        return
    print "Error: %s is already defined in hostbase" % field
    if '-s' in sys.argv:
        sys.exit(1)

def checkformat(values, indices):
    """Ensures file contains all necessary attributes in order """
    filelist = [pair[0] for pair in values]

#    lines = len(filelist)

    for index in indices:
        filelist = filelist[index:]
        if filelist[0:14] != host_attribs:
            # figure out what to do here
            return False
        else:
            # process rest of host attributes
            try:
                next = filelist[1:].index('hostname')
                remaining = filelist[14:next+1]
            except:
                remaining = filelist[14:]
            needfields = ['mac_addr', 'hdwr_type', 'ip_addr']
            if [item for item in needfields if item not in remaining]:
                return False
    return True


if __name__ == '__main__':

    # argument handling for batchadd
    try:
        fd = open(sys.argv[1], 'r')
    except (IndexError, IOError):
        print "\nUsage: batchadd.py filename\n"
        sys.exit()

    lines = fd.readlines()
    # splits and strips lines into (attribute, value)
    info = [[item.strip() for item in line.split("->")] for line in lines
            if line.lstrip(' ')[0] != '#' and line != '\n']

    if info[0][0] == 'mx' and info[1][0] == 'priority':
        mx, created = MX.objects.get_or_create(mx=info[0][1], priority=info[1][1])
        info = info[2:]
    
    else:
        mx, created = MX.objects.get_or_create(mx=DEFAULT_MX, priority=PRIORITY)
    if created:
        mx.save()

    hostindices = [num for num in range(0, len(info)) if info[num][0] == 'hostname']

    if not checkformat(info, hostindices):
        print "Error: file format"
        sys.exit()

#################

    for host in hostindices:
        try:
            host = Host.objects.get(hostname=info[host][1])
            handle_error(info[host][1])
        except:
            # do something here
            pass

    macindices = [num for num in range(0, len(info)) if info[num][0] == 'mac_addr']
    for mac_addr in macindices:
        try:
            host = Interface.objects.get(mac_addr=info[mac_addr][1])
            handle_error(info[mac_addr][1])
        except:
            # do something here
            pass

    for host in hostindices:
        blank = Host()
        for attrib in host_attribs:
            pair = info.pop(0)
            if pair[0] == 'dhcp' or pair[0] == 'outbound_smtp':
                if pair[1] == 'y':
                    blank.__dict__[pair[0]] = 1
                else:
                    blank.__dict__[pair[0]] = 0
            elif pair[0] == 'expiration_date':
                (year, month, day) = pair[1].split("-")
                blank.expiration_date = date(int(year), int(month), int(day))
            else:
                blank.__dict__[pair[0]] = pair[1]
        blank.status = 'active'
        blank.save()
        newhostname = blank.hostname.split(".")[0]
        newdomain = blank.hostname.split(".", 1)[1]
        while info and info[0][0] != 'hostname':
            if info[0][0] == 'mac_addr':
                pair = info.pop(0)
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
            
