'''This file provides the Hostbase plugin. It manages dns/dhcp/nis host information'''
__revision__ = '$Revision$'

from lxml.etree import XML, SubElement
from Cheetah.Template import Template
from Bcfg2.Server.Plugin import Plugin, PluginExecutionError, PluginInitError, DirectoryBacked
from time import strftime
from sets import Set
import re

import logging

logger = logging.getLogger('Bcfg2.Plugins.Hostbase')

class DataNexus(DirectoryBacked):
    '''DataNexus is an object that watches multiple files and
    handles changes in an intelligent fashion.'''
    __name__ = 'DataNexus'

    def __init__(self, path, filelist, fam):
        self.files = filelist
        DirectoryBacked.__init__(self, path, fam)
        
    def HandleEvent(self, event):
        '''Trap adds and updates, else call baseclass HandleEvent'''
        action = event.code2str()
        if action in ['exists', 'created']:
            if (event.filename != self.name) and (event.filename not in self.files):
                logger.info("%s:Got event for unexpected file %s" % (self.__name__, event.filename))
                return
        DirectoryBacked.HandleEvent(self, event)
        if action != 'endExist' and event.filename != self.name:
            self.rebuildState(event)

    def rebuildState(self, event):
        '''This function is called when underlying data has changed'''
        pass

class Hostbase(Plugin, DataNexus):
    '''The Hostbase plugin handles host/network info'''
    __name__ = 'Hostbase'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    filepath = '/etc/bind'

    def __init__(self, core, datastore):
        self.ready = False
        files = ['zones.xml', 'hostbase.xml', 'hostbase-dns.xml', 'hostbase-dhcp.xml']
        Plugin.__init__(self, core, datastore)
        try:
            DataNexus.__init__(self, datastore + '/Hostbase/data',
                               files, self.core.fam)
        except:
            logger.error("Failed to load data directory")
            raise PluginInitError
        self.xdata = {}
        self.filedata = {}
        self.dnsservers = ['scotty.mcs.anl.gov']
        self.dhcpservers = ['thwap.mcs.anl.gov', 'squeak.mcs.anl.gov']
        self.templates = {'zone':Template(open(self.data + '/templates/' + 'zonetemplate.tmpl').read()),
                          'reversesoa':Template(open(self.data + '/templates/' + 'reversesoa.tmpl').read()),
                          'named':Template(open(self.data + '/templates/' + 'namedtemplate.tmpl').read()),
                          'reverseapp':Template(open(self.data + '/templates/' + 'reverseappend.tmpl').read()),
                          'dhcp':Template(open(self.data + '/templates/' + 'dhcpd_template.tmpl').read()),
                          'hosts':Template(open(self.data + '/templates/' + 'hosts.tmpl').read()),
                          'hostsapp':Template(open(self.data + '/templates/' + 'hostsappend.tmpl').read())}
        self.Entries['ConfigFile'] = {}

    def FetchFile(self, entry, metadata):
        '''Return prebuilt file data'''
        fname = entry.get('name').split('/')[-1]
        if not self.filedata.has_key(fname):
            raise PluginExecutionError
        perms = {'owner':'root', 'group':'root', 'perms':'644'}
        [entry.attrib.__setitem__(key, value) for (key, value) in perms.iteritems()]
        entry.text = self.filedata[fname]

    def BuildStructures(self, metadata):
        '''Build hostbase bundle'''
        if metadata.hostname in self.dnsservers or metadata.hostname in self.dhcpservers:
            output = []
            if metadata.hostname in self.dnsservers:
                dnsbundle = XML(self.entries['hostbase-dns.xml'].data)
                for configfile in self.Entries['ConfigFile']:
                    if re.search('/etc/bind/', configfile):
                        SubElement(dnsbundle, "ConfigFile", name=configfile)
                output.append(dnsbundle)
            if metadata.hostname in self.dhcpservers:
                dhcpbundle = XML(self.entries['hostbase-dhcp.xml'].data)
                output.append(dhcpbundle)
            return output
        else: 
            return []

    def rebuildState(self, event):
        '''Pre-cache all state information for hostbase config files'''
        def get_serial(zone):
            '''I think this does the zone file serial number hack but whatever'''
            todaydate = (strftime('%Y%m%d'))
            try:
                if todaydate == zone.get('serial')[:8]:
                    serial = int(zone.get('serial')) + 1
                else:
                    serial = int(todaydate) * 100
                return str(serial)
            except (KeyError):
                serial = int(todaydate) * 100
                return str(serial)

        if self.entries.has_key(event.filename) and not self.xdata.has_key(event.filename):
            self.xdata[event.filename] = XML(self.entries[event.filename].data)
        if [item for item in self.files if not self.entries.has_key(item)]:
            return
        # we might be able to rebuild data more sparsely,
        # but hostbase.xml is the only one that will really change often
        # rebuild zoneinfo
        hosts = {}
        zones = self.xdata['zones.xml']
        hostbase = self.xdata['hostbase.xml']
        ## this now gets all hosts associated with the zone file being initialized
        ## all ip addresses and cnames are grabbed from each host and passed to the appropriate template
        for zone in zones:
            hosts[zone.get('domain')] = []
        for host in hostbase:
            if host.get('domain') in hosts:
                hosts[host.get('domain')].append(host)
        for zone in zones:
            zonehosts = []
            for host in hosts[zone.get('domain')]:
                hostname = host.attrib['hostname']
                ipnodes = host.findall("interface/ip")
                #gets all the forward look up stuff
                [zonehosts.append((namenode.get('name').split(".")[0], ipnode.get('ip'),
                                   namenode.findall('mx')))
                 for ipnode in ipnodes
                 for namenode in ipnode]
                #gets cname stuff
                [zonehosts.append((cnamenode.get('cname') + '.', namenode.get('name').split('.')[0],  None))
                 for namenode in host.findall("interface/ip/name")
                 for cnamenode in namenode.findall("cname")
                 if (cnamenode.get('cname').split(".")[0], namenode.get('name').split('.')[0],  None) not in zonehosts
                 and cnamenode.get('cname') is not None]

            zonehosts.sort()
            self.templates['zone'].zone = zone
            self.templates['zone'].root = zones
            self.templates['zone'].hosts = zonehosts
            self.filedata[zone.get('domain')] = str(self.templates['zone'])
            self.Entries['ConfigFile']["%s/%s" % (self.filepath, zone.get('domain'))] = self.FetchFile
        # now all zone forward files are built
        filelist = []
        three_subnet = [ip.get('ip').rstrip('0123456789').rstrip('.')
                        for ip in hostbase.findall('host/interface/ip')]
        three_subnet_set = Set(three_subnet)
        two_subnet = [subnet.rstrip('0123456789').rstrip('.')
                      for subnet in three_subnet_set]
        two_subnet_set = Set(two_subnet)
        filelist = [each for each in two_subnet_set
                    if two_subnet.count(each) > 1]
        [filelist.append(each) for each in three_subnet_set
         if each.rstrip('0123456789').rstrip('.') not in filelist]
        
        reversenames = []
        for filename in filelist:
            towrite = filename.split('.')
            towrite.reverse()
            reversename = '.'.join(towrite)
            self.templates['reversesoa'].inaddr = reversename
            self.templates['reversesoa'].zone = zone
            self.templates['reversesoa'].root = self.xdata['zones.xml']
            self.filedata['%s.rev' % reversename] = str(self.templates['reversesoa'])
            reversenames.append(reversename)

        self.templates['named'].zones = self.xdata['zones.xml']
        self.templates['named'].reverses = reversenames
        self.filedata["named.conf"] = str(self.templates['named'])
        self.Entries['ConfigFile']["%s/%s" % (self.filepath, 'named.conf')] = self.FetchFile

        reversenames.sort()
        for filename in reversenames:
            originlist = []
            reversehosts = []
            towrite = filename.split(".")
            towrite.reverse()
            if len(towrite) > 2:
                [reversehosts.append((ipnode.attrib['ip'].split("."), host.attrib['hostname'],
                                      host.attrib['domain'], ipnode.get('num'), None))
                 for host in self.xdata['hostbase.xml']
                 for ipnode in host.findall("interface/ip")
                 if ipnode.attrib['ip'].split(".")[:3] == towrite]
                self.templates['reverseapp'].hosts = reversehosts
                self.templates['reverseapp'].inaddr = filename
                self.templates['reverseapp'].fileorigin = None
                self.filedata["%s.rev" % filename] += str(self.templates['reverseapp'])
            else:
                [reversehosts.append((ipnode.attrib['ip'].split("."), host.attrib['hostname'],
                                      host.attrib['domain'], ipnode.get('num'), None))
                 for host in self.xdata['hostbase.xml']
                 for ipnode in host.findall("interface/ip")
                 if ipnode.attrib['ip'].split(".")[:2] == towrite]

                [originlist.append(".".join([reversehost[0][2], reversehost[0][1], reversehost[0][0]]))
                 for reversehost in reversehosts
                 if ".".join([reversehost[0][2], reversehost[0][1], reversehost[0][0]]) not in originlist]

                reversehosts.sort()
                originlist.sort()
                for origin in originlist:
                    outputlist = []
                    [outputlist.append(reversehost)
                     for reversehost in reversehosts
                     if ".".join([reversehost[0][2], reversehost[0][1], reversehost[0][0]]) == origin] 
                    self.templates['reverseapp'].fileorigin = filename
                    self.templates['reverseapp'].hosts = outputlist
                    self.templates['reverseapp'].inaddr = origin
                    self.filedata["%s.rev" % filename] += str(self.templates['reverseapp'])
            self.Entries['ConfigFile']["%s/%s.rev" % (self.filepath, filename)] = self.FetchFile
        self.buildDHCP()
        self.buildHosts()
        self.buildHostsLPD()
        self.buildPrinters()
        self.buildNetgroups()

    def buildDHCP(self):
        '''Pre-build dhcpd.conf and stash in the filedata table'''
        if 'hostbase.xml' not in self.xdata.keys():
            print "not running before hostbase is cached"
            return
        hostbase = self.xdata['hostbase.xml']
        dhcphosts = [host for host in hostbase if host.find('dhcp').get('dhcp') == 'y'
                     and host.find("interface").attrib['mac'] != 'float'
                     and host.find("interface").attrib['mac'] != ""
                     and host.find("interface").attrib['mac'] != "unknown"]

        numips = 0
        hosts = []
        for host in dhcphosts:
            if len(host.findall("interface")) == 1 and len(host.findall("interface/ip")) == 1:
                hosts.append([host.attrib['hostname'], host.attrib['domain'], \
                            host.find("interface").attrib['mac'], \
                            host.find("interface/ip").attrib['ip']])
            else:
                count = 0
                for interface in host.findall('interface'):
                    if count == 0 and interface.find("ip") is not None:
                        hostdata = [host.attrib['hostname'], host.attrib['domain'],
                                    interface.attrib['mac'], interface.find("ip").attrib['ip']]
                    elif count != 0 and interface.find("ip") is not None:
                        hostdata = [host.attrib['hostname'], "-".join([host.attrib['domain'], str(count)]),
                                    interface.attrib['mac'], interface.find("ip").attrib['ip']]
                    if len(interface.findall("ip")) > 1:
                        for ip in interface.findall("ip")[1:]:
                            hostdata[3] = ", ".join([hostdata[3], ip.attrib['ip']])
                    count += 1
                    hosts.append(hostdata)
            
            numips += len(host.findall("interface/ip"))

        hosts.sort(lambda x, y: cmp(x[0], y[0]))
        self.templates['dhcp'].hosts = hosts
        self.templates['dhcp'].numips = numips
        self.templates['dhcp'].timecreated = strftime("%a %b %d %H:%M:%S %Z %Y")
        self.filedata['dhcpd.conf'] = str(self.templates['dhcp'])
        self.Entries['ConfigFile']['/etc/dhcpd.conf'] = self.FetchFile

    def buildHosts(self):
        '''This will rebuild the hosts file to include all important machines'''
        hostbase = self.xdata['hostbase.xml']
        domains = [host.get('domain') for host in hostbase]
        domains_set = Set(domains)
        domain_data = [(domain, domains.count(domain)) for domain in domains_set]
        domain_data.sort()
        ips = [(ip, host) for host in hostbase.findall('host')
               for ip in host.findall("interface/ip")]
        three_octets = [ip[0].get('ip').rstrip('0123456789').rstrip('.')
                        for ip in ips]
        three_octets_set = list(Set(three_octets))
        three_sort = [tuple([int(num) for num in each.split('.')]) for each in three_octets_set]
        three_sort.sort()
        three_octets_set = ['.'.join([str(num) for num in each]) for each in three_sort]
        three_octets_data = [(octet, three_octets.count(octet))
                             for octet in three_octets_set]
        append_data = [(subnet, [ip for ip in ips \
                                 if ip[0].get('ip').rstrip("0123456789").rstrip('.')
                                 == subnet[0]]) for subnet in three_octets_data]
        for each in append_data:
            each[1].sort(lambda x, y: cmp(int(x[0].get('ip').split('.')[-1]), int(y[0].get('ip').split('.')[-1])))
        two_octets = [ip.rstrip('0123456789').rstrip('.') for ip in three_octets]
        two_octets_set = list(Set(two_octets))
        two_sort = [tuple([int(num) for num in each.split('.')]) for each in two_octets_set]
        two_sort.sort()
        two_octets_set = ['.'.join([str(num) for num in each]) for each in two_sort]
        two_octets_data = [(octet, two_octets.count(octet)) for octet in two_octets_set]
        self.templates['hosts'].domain_data = domain_data
        self.templates['hosts'].three_octets_data = three_octets_data
        self.templates['hosts'].two_octets_data = two_octets_data
        self.templates['hosts'].three_octets = len(three_octets)
        self.templates['hosts'].timecreated = strftime("%a %b %d %H:%M:%S %Z %Y")
        self.filedata['hosts'] = str(self.templates['hosts'])
        for subnet in append_data:
            self.templates['hostsapp'].ips = subnet[1]
            self.templates['hostsapp'].subnet = subnet[0]
            self.filedata['hosts'] += str(self.templates['hostsapp'])
        self.Entries['ConfigFile']['/mcs/etc/hosts'] = self.FetchFile


    def buildPrinters(self):
        '''this will rebuild the printers.data file used in
        our local printers script'''
        header = """#  This file is automatically generated. DO NOT EDIT IT!
#  This datafile is for use with /mcs/bin/printers.
#
Name            Room        User          Type                      Notes
==============  ==========  ============  ========================  ====================
"""

        printers = [host for host in self.xdata['hostbase.xml']
                    if host.find('whatami').get('whatami') == "printer"
                    and host.get('domain') == 'mcs.anl.gov']
        self.filedata['printers.data'] = header
        output_list = []
        for printer in printers:
            if printer.find('printq').get('printq'):
                for printq in re.split(',[ ]*', printer.find('printq').get('printq')):
                    output_list.append((printq, printer.find('room').get('room'), printer.find('user').get('user'),
                                        printer.find('model').get('model'), printer.find('note').get('note')))
        output_list.sort()
        for printer in output_list:
            self.filedata['printers.data'] += ("%-16s%-12s%-14s%-26s%s\n" % printer)
        self.Entries['ConfigFile']['/mcs/etc/printers.data'] = self.FetchFile

    def buildHostsLPD(self):
        '''this rebuilds the hosts.lpd file'''
        header = """+@machines
+@all-machines
achilles.ctd.anl.gov
raven.ops.anl.gov
seagull.hr.anl.gov
parrot.ops.anl.gov
condor.ops.anl.gov
delphi.esh.anl.gov
anlcv1.ctd.anl.gov
anlvms.ctd.anl.gov
olivia.ctd.anl.gov\n\n"""

        hostbase = self.xdata['hostbase.xml']
        redmachines = [".".join([host.get('hostname'), host.get('domain')])
                       for host in hostbase if host.find('netgroup').get('netgroup') == 'red']
        winmachines = [".".join([host.get('hostname'), host.get('domain')])
                       for host in hostbase if host.find('netgroup').get('netgroup') == 'win']
        redmachines += [name.get('name') for host in hostbase
                        for name in host.findall('interface/ip/name')
                        if host.find('netgroup').get('netgroup') == 'red' and name.get('only') != 'no']
        winmachines += [name.get('name') for host in hostbase
                        for name in host.findall('interface/ip/name')
                        if host.find('netgroup').get('netgroup') == 'win' and name.get('only') != 'no']
        redmachines.sort()
        winmachines.sort()
        self.filedata['hosts.lpd'] = header
        for machine in redmachines:
            self.filedata['hosts.lpd'] += machine + "\n"
        self.filedata['hosts.lpd'] += "\n"
        for machine in winmachines:
            self.filedata['hosts.lpd'] += machine + "\n"
        self.Entries['ConfigFile']['/mcs/etc/hosts.lpd'] = self.FetchFile

    def buildNetgroups(self):
        '''this rebuilds the many different files that will eventually
        get post processed and converted into a ypmap for netgroups'''
        header = """###################################################################
#  This file lists hosts in the '%s' machine netgroup, it is
#  automatically generated. DO NOT EDIT THIS FILE! To update
#  the hosts in this file, edit hostbase and do a 'make nets'
#  in /mcs/adm/hostbase.
#
#  Number of hosts in '%s' machine netgroup: %i
#\n\n"""

        netgroups = {}
        for host in self.xdata['hostbase.xml']:
            if host.find('netgroup').get('netgroup') == "" or host.find('netgroup').get('netgroup')== 'none':
                continue
            if host.find('netgroup').get('netgroup') not in netgroups:
                netgroups.update({host.find('netgroup').get('netgroup') :
                                  [".".join([host.get('hostname'), host.get('domain')])]})
            else:
                netgroups[host.find('netgroup').get('netgroup')].append(".".join([host.get('hostname'),
                                                                                  host.get('domain')]))

            for name in host.findall('interface/ip/name'):
                if name.get('only') != 'no':
                    netgroups[host.find('netgroup').get('netgroup')].append(name.get('name'))

        for netgroup in netgroups:
            self.filedata["%s-machines" % netgroup] = header % (netgroup, netgroup, len(netgroups[netgroup]))
            netgroups[netgroup].sort()
            for each in netgroups[netgroup]:
                self.filedata["%s-machines" % netgroup] += each + "\n"
            self.Entries['ConfigFile']["/var/yp/netgroups/%s-machines" % netgroup] = self.FetchFile

    def dumpXML(self):
        '''this just dumps the info in the hostbase.xml file to be used
        with external programs'''
        self.filedata['hostbase.xml'] = self.xdata['hostbase.xml']
        self.Entries['ConfigFile']['/etc/hostbase.xml'] = self.FetchFile

