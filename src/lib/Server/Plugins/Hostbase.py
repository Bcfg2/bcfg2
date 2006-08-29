'''This file provides the Hostbase plugin. It manages dns/dhcp/nis host information'''
__revision__ = '$Revision$'

from lxml.etree import Element, SubElement
from django.db import connection
from syslog import syslog, LOG_INFO
from Cheetah.Template import Template
from Bcfg2.Server.Plugin import Plugin, PluginExecutionError, PluginInitError, DirectoryBacked
from time import strftime
from sets import Set
import re


## class DataNexus(DirectoryBacked):
##     '''DataNexus is an object that watches multiple files and
##     handles changes in an intelligent fashion.'''
##     __name__ = 'DataNexus'

##     def __init__(self, path, filelist, fam):
##         self.files = filelist
##         DirectoryBacked.__init__(self, path, fam)
        
##     def HandleEvent(self, event):
##         '''Trap adds and updates, else call baseclass HandleEvent'''
##         action = event.code2str()
##         if action in ['exists', 'created']:
##             if (event.filename != self.name) and (event.filename not in self.files):
##                 syslog(LOG_INFO, "%s:Got event for unexpected file %s" % (self.__name__, event.filename))
##                 return
##         DirectoryBacked.HandleEvent(self, event)
##         if action != 'endExist' and event.filename != self.name:
##             self.rebuildState(event)

##     def rebuildState(self, event):
##         '''This function is called when underlying data has changed'''
##         pass

class Hostbase(Plugin):
    '''The Hostbase plugin handles host/network info'''
    __name__ = 'Hostbase'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    filepath = '/etc/bind'

    def __init__(self, core, datastore):

        self.ready = False
        Plugin.__init__(self, core, datastore)
##         try:
##             DataNexus.__init__(self, datastore + '/Hostbase/data',
##                                files, self.core.fam)
##         except:
##             self.LogError("Failed to load data directory")
##             raise PluginInitError
        self.filedata = {}
        self.dnsservers = []
        self.dhcpservers = []
        self.templates = {'zone':Template(open(self.data + '/templates/' + 'zone.tmpl').read()),
                          'reversesoa':Template(open(self.data + '/templates/' + 'reversesoa.tmpl').read()),
                          'named':Template(open(self.data + '/templates/' + 'named.tmpl').read()),
                          'reverseapp':Template(open(self.data + '/templates/' + 'reverseappend.tmpl').read()),
                          'dhcp':Template(open(self.data + '/templates/' + 'dhcpd.tmpl').read()),
                          'hosts':Template(open(self.data + '/templates/' + 'hosts.tmpl').read()),
                          'hostsapp':Template(open(self.data + '/templates/' + 'hostsappend.tmpl').read()),
                          }
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
        if metadata.hostname not in self.dnsservers or metadata.hostname not in self.dhcpservers:
            return []
        output = Element("Bundle", name='hostbase')
        if metadata.hostname in self.dnsservers:
            for configfile in self.Entries['ConfigFile']:
                if re.search('/etc/bind/', configfile):
                    SubElement(output, "ConfigFile", name=configfile)
        if metadata.hostname in self.dhcpservers:
            SubElement(output, "ConfigFile", name="/etc/dhcpd.conf")
        return [output]

    def rebuildState(self):
        '''Pre-cache all state information for hostbase config files'''

        cursor = connection.cursor()

        cursor.execute("SELECT id, serial FROM hostbase_zone")
        zones = cursor.fetchall()

        for zone in zones:
        # update the serial number for all zone files
            todaydate = (strftime('%Y%m%d'))
            try:
                if todaydate == str(zone[1])[:8]:
                    serial = zone[1] + 1
                else:
                    serial = int(todaydate) * 100
            except (KeyError):
                serial = int(todaydate) * 100
            cursor.execute("""UPDATE hostbase_zone SET serial = \'%s\' WHERE id = \'%s\'""" % (str(serial), zone[0]))

        cursor.execute("SELECT * FROM hostbase_zone")
        zones = cursor.fetchall()

        iplist = []
        hosts = {}

        for zone in zones:
            if zone[1] == 'mcs.anl.gov':
                reversezone = zone
                cursor.execute("""SELECT n.name FROM hostbase_zone_nameservers z
                INNER JOIN hostbase_nameserver n ON z.nameserver_id = n.id
                WHERE z.zone_id = \'%s\'""" % zone[0])
                mcs_nameservers = cursor.fetchall()


        for zone in zones:
            self.templates['zone'].zone = zone
            cursor.execute("""SELECT n.name FROM hostbase_zone_nameservers z
            INNER JOIN hostbase_nameserver n ON z.nameserver_id = n.id
            WHERE z.zone_id = \'%s\'""" % zone[0])
            self.templates['zone'].nameservers = cursor.fetchall()
            cursor.execute("""SELECT i.ip_addr FROM hostbase_zone_addresses z
            INNER JOIN hostbase_ip i ON z.ip_id = i.id
            WHERE z.zone_id = \'%s\'""" % zone[0])
            self.templates['zone'].addresses = cursor.fetchall()
            cursor.execute("""SELECT m.priority, m.mx FROM hostbase_zone_mxs z
            INNER JOIN hostbase_mx m ON z.mx_id = m.id
            WHERE z.zone_id = \'%s\'""" % zone[0])
            self.templates['zone'].mxs = cursor.fetchall()
            self.filedata[zone[1]] = str(self.templates['zone'])

            querystring = """SELECT h.hostname, p.ip_addr,
            n.name, c.cname, m.priority, m.mx
            FROM (((((hostbase_host h INNER JOIN hostbase_interface i ON h.id = i.host_id)
            INNER JOIN hostbase_ip p ON i.id = p.interface_id)
            INNER JOIN hostbase_name n ON p.id = n.ip_id)
            INNER JOIN hostbase_name_mxs x ON n.id = x.name_id)
            INNER JOIN hostbase_mx m ON m.id = x.mx_id)
            LEFT JOIN hostbase_cname c ON n.id = c.name_id
            WHERE h.hostname LIKE '%%%%%s' AND h.status = 'active'
            ORDER BY h.hostname, n.name, p.ip_addr
            """ % zone[1]
            cursor.execute(querystring)
            zonehosts = cursor.fetchall()
##             hosts[zone[1]] = zonehosts
            prevhost = (None, None, None, None)
            for host in zonehosts:
                if not host[0].split(".", 1)[1] == zone[1]:
                    continue
                if not prevhost[1] == host[1] or not prevhost[2] == host[2]:
                    self.filedata[zone[1]] += ("%-32s%-10s%-32s\n" %                   
                                           (host[2].split(".", 1)[0], 'A', host[1]))
                    self.filedata[zone[1]] += ("%-32s%-10s%-3s%-29s\n" %                   
                                           ('', 'MX', host[4], host[5].split(".", 1)[0]))
                if host[3]:
                    if host[3].split(".", 1)[1] == zone[1]:
                        self.filedata[zone[1]] += ("%-32s%-10s%-32s\n" %                   
                                               (host[3].split(".", 1)[0],
                                                'CNAME',host[2].split(".", 1)[0]))
                    else:
                        self.filedata[zone[1]] += ("%-32s%-10s%-32s\n" %                   
                                               (host[3]+".",
                                                'CNAME',
                                                host[2].split(".", 1)[0]))
                prevhost = host
            self.filedata[zone[1]] += ("\n\n%s" % zone[9])

            self.Entries['ConfigFile']["%s/%s" % (self.filepath, zone[1])] = self.FetchFile


        filelist = []
        cursor.execute("""
        SELECT ip_addr FROM hostbase_ip ORDER BY ip_addr
        """)
        three_subnet = [ip[0].rstrip('0123456789').rstrip('.') \
                        for ip in cursor.fetchall()]
        three_subnet_set = Set(three_subnet)
        two_subnet = [subnet.rstrip('0123456789').rstrip('.') \
                      for subnet in three_subnet_set]
        two_subnet_set = Set(two_subnet)
        filelist = [each for each in two_subnet_set \
                    if two_subnet.count(each) > 1]
        for each in three_subnet_set:
            if each.rstrip('0123456789').rstrip('.') not in filelist:
                filelist.append(each)

        reversenames = []
        for filename in filelist:
            towrite = filename.split('.')
            towrite.reverse()
            reversename = '.'.join(towrite)
            self.templates['reversesoa'].inaddr = reversename
            self.templates['reversesoa'].zone = reversezone
            self.templates['reversesoa'].nameservers = mcs_nameservers
            self.filedata['%s.rev' % reversename] = str(self.templates['reversesoa'])
            reversenames.append((reversename, filename))

        ## here's where the named.conf file gets written
        self.templates['named'].zones = zones
        self.templates['named'].reverses = reversenames
        self.filedata['named.conf'] = str(self.templates['named'])
        self.Entries['ConfigFile']['%s/named.conf' % self.filepath] = self.FetchFile

        reversenames.sort()
        for filename in reversenames:
            originlist = []
            cursor.execute("""
            SELECT h.hostname, p.ip_addr, p.num FROM ((hostbase_host h
            INNER JOIN hostbase_interface i ON h.id = i.host_id)
            INNER JOIN hostbase_ip p ON i.id = p.interface_id)
            WHERE p.ip_addr LIKE '%s%%%%' AND h.status = 'active' ORDER BY p.ip_addr
            """ % filename[1])
            reversehosts = cursor.fetchall()
            if len(filename[0].split(".")) == 2:
                [originlist.append((".".join([ip[1].split(".")[2], filename[0]]),
                                    ".".join([filename[1], ip[1].split(".")[2]])))
                 for ip in reversehosts
                 if (".".join([ip[1].split(".")[2], filename[0]]),
                     ".".join([filename[1], ip[1].split(".")[2]])) not in originlist]
                for origin in originlist:
                    hosts = [host.__add__((host[1].split("."), host[0].split(".", 1)))
                             for host in reversehosts
                             if host[1].rstrip('0123456789').rstrip('.') == origin[1]]
                    self.templates['reverseapp'].hosts = hosts
                    self.templates['reverseapp'].inaddr = origin[0]
                    self.templates['reverseapp'].fileorigin = filename[0]
                    self.filedata['%s.rev' % filename[0]] += str(self.templates['reverseapp'])
            else:
                originlist = [filename[0]]
            hosts = [host.__add__((host[1].split("."), host[0].split(".", 1)))
                     for host in reversehosts]
            self.templates['reverseapp'].hosts = hosts
            self.templates['reverseapp'].inaddr = filename[0]
            self.templates['reverseapp'].fileorigin = None
            self.filedata['%s.rev' % filename[0]] += str(self.templates['reverseapp'])
            self.Entries['ConfigFile']['%s/%s.rev' % (self.filepath, filename[0])] = self.FetchFile

        self.buildDHCP()
        self.buildHosts()
        self.buildHostsLPD()
        self.buildPrinters()
        self.buildNetgroups()

    def buildDHCP(self):
        '''Pre-build dhcpd.conf and stash in the filedata table'''

        # fetches all the hosts with DHCP == True
        cursor = connection.cursor()
        cursor.execute("""
        SELECT hostname, mac_addr, ip_addr
        FROM (hostbase_host h INNER JOIN hostbase_interface i ON h.id = i.host_id)
        INNER JOIN hostbase_ip ip ON i.id = ip.interface_id
        WHERE h.dhcp=1 AND h.status = 'active'
        ORDER BY h.hostname, i.mac_addr
        """)

        dhcphosts = cursor.fetchall()
        count = 0
        hosts = []
        hostdata = [dhcphosts[0][0], dhcphosts[0][1], dhcphosts[0][2]]
        for x in range(1, len(cursor.fetchall())-1):
            # if an interface has 2 or more ip addresses
            # adds the ip to the current interface
            if hostdata[0] == dhcphosts[x][0] and hostdata[1] == dhcphosts[x][1]:
                hostdata[2] = ", ".join([hostdata[2], dhcphosts[x][2]])
            # if a host has 2 or more interfaces
            # writes the current one and grabs the next
            elif hostdata[0] == dhcphosts[x][0]:
                hosts.append(hostdata)
                count += 1
                hostdata = [dhcphosts[x][0], dhcphosts[x][1], dhcphosts[x][2]]
            # new host found, writes current data to the template
            else:
                if count:
                    hostdata[0] = "-".join([hostdata[0], str(count)])
                hosts.append(hostdata)
                count = 0
                hostdata = [dhcphosts[x][0], dhcphosts[x][1], dhcphosts[x][2]]
        #makes sure the last of the data gets written out
        if hostdata not in hosts:
            hosts.append(hostdata)

        self.templates['dhcp'].hosts = hosts
        self.templates['dhcp'].numips = len(hosts)
        self.templates['dhcp'].timecreated = strftime("%a %b %d %H:%M:%S %Z %Y")

        self.filedata['dhcpd.conf'] = str(self.templates['dhcp'])
        self.Entries['ConfigFile']['/etc/dhcpd.conf'] = self.FetchFile


    def buildHosts(self):

        append_data = []

        cursor = connection.cursor()
        cursor.execute("""
        SELECT hostname FROM hostbase_host ORDER BY hostname
        """)
        hostbase = cursor.fetchall()
        domains = [host[0].split(".", 1)[1] for host in hostbase]
        domains_set = Set(domains)
        domain_data = [(domain, domains.count(domain)) for domain in domains_set]
        domain_data.sort()

        cursor.execute("""
        SELECT ip_addr FROM hostbase_ip ORDER BY ip_addr
        """)
        ips = cursor.fetchall()
        three_octets = [ip[0].rstrip('0123456789').rstrip('.') \
                        for ip in ips]
        three_octets_set = Set(three_octets)
        three_octets_data = [(octet, three_octets.count(octet)) \
                             for octet in three_octets_set]
        three_octets_data.sort()

        for three_octet in three_octets_data:
            querystring = """SELECT h.hostname, h.primary_user,
            p.ip_addr, n.name, c.cname
            FROM (((hostbase_host h INNER JOIN hostbase_interface i ON h.id = i.host_id)
            INNER JOIN hostbase_ip p ON i.id = p.interface_id)
            INNER JOIN hostbase_name n ON p.id = n.ip_id)
            LEFT JOIN hostbase_cname c ON n.id = c.name_id
            WHERE p.ip_addr LIKE \'%s%%%%\' AND h.status = 'active'
            ORDER BY p.ip_addr""" % three_octet[0]
            cursor.execute(querystring)
            append_data.append((three_octet, cursor.fetchall()))

        two_octets = [ip.rstrip('0123456789').rstrip('.') for ip in three_octets]
        two_octets_set = Set(two_octets)
        two_octets_data = [(octet, two_octets.count(octet))
                           for octet in two_octets_set]
        two_octets_data.sort()

        self.templates['hosts'].domain_data = domain_data
        self.templates['hosts'].three_octets_data = three_octets_data
        self.templates['hosts'].two_octets_data = two_octets_data
        self.templates['hosts'].three_octets = len(three_octets)
        self.filedata['hosts'] = str(self.templates['hosts'])

        for subnet in append_data:
            ips = []
            simple = True
            namelist = [subnet[1][0][3]]
            cnamelist = []
            if subnet[1][0][4]:
                cnamelist.append(subnet[1][0][4])
                simple = False
            appenddata = subnet[1][0]
            for ip in subnet[1][1:]:
                if appenddata[2] == ip[2]:
                    namelist.append(ip[3])
                    if ip[4]:
                        cnamelist.append(ip[4])
                        simple = False
                    appenddata = ip
                else:
                    if appenddata[0] == ip[0]:
                        simple = False
                    ips.append((appenddata[2], appenddata[0], namelist,
                                cnamelist, simple, appenddata[1]))
                    appenddata = ip
                    simple = True
                    namelist = [ip[3]]
                    cnamelist = []
                    if ip[4]:
                        cnamelist.append(ip[4])
                        simple = False
            ips.append((appenddata[2], appenddata[0], namelist,
                        cnamelist, simple, appenddata[1]))
            self.templates['hostsapp'].subnet = subnet[0]
            self.templates['hostsapp'].ips = ips
            self.filedata['hosts'] += str(self.templates['hostsapp'])
        self.Entries['ConfigFile']['/mcs/etc/hosts'] = self.FetchFile

    def buildPrinters(self):
        """The /mcs/etc/printers.data file"""
        header = """#  This file is automatically generated. DO NOT EDIT IT!
        #  To update the contents of this file execute a 'make printers'
        #  and then an 'install printers' in /mcs/adm/hostbase as root
        #  on antares. This datafile is for use with /mcs/bin/printers.
        #
        Name            Room        User                            Type                      Notes
        ==============  ==========  ==============================  ========================  ====================
        """

        cursor = connection.cursor()
        # fetches all the printers from the database
        cursor.execute("""
        SELECT printq, location, primary_user, comments
        FROM hostbase_host
        WHERE whatami='printer' AND printq <> '' AND status = 'active'
        ORDER BY printq
        """)
        printers = cursor.fetchall()

        printersfile = header
        for printer in printers:
            # splits up the printq line and gets the
            # correct description out of the comments section
            temp = printer[3].split('\n')
            for printq in re.split(',[ ]*', printer[0]):
                if len(temp) > 1:
                    printersfile += ("%-16s%-12s%-32s%-26s%s\n" %
                                     (printq, printer[1], printer[2], temp[1], temp[0]))
                else:
                    printersfile += ("%-16s%-12s%-32s%-26s%s\n" %
                                     (printq, printer[1], printer[2], '', printer[3]))
        print 'Done!'
        self.filedata['printers.data'] = printersfile
        self.Entries['ConfigFile']['/mcs/etc/printers.data'] = self.FetchFile

    def buildHostsLPD(self):
        """Creates the /mcs/etc/hosts.lpd file"""
        
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
        
        cursor = connection.cursor()
        cursor.execute("""
        SELECT hostname FROM hostbase_host WHERE netgroup=\"red\" AND status = 'active'
        ORDER BY hostname""")
        redmachines = list(cursor.fetchall())
        cursor.execute("""
        SELECT n.name FROM ((hostbase_host h INNER JOIN hostbase_interface i ON h.id = i.host_id)
        INNER JOIN hostbase_ip p ON i.id = p.interface_id) INNER JOIN hostbase_name n ON p.id = n.ip_id
        WHERE netgroup=\"red\" AND n.only=1 AND h.status = 'active'
        """)
        redmachines.extend(list(cursor.fetchall()))
        cursor.execute("""
        SELECT hostname FROM hostbase_host WHERE netgroup=\"win\" AND status = 'active'
        ORDER BY hostname""")
        winmachines = list(cursor.fetchall())
        cursor.execute("""
        SELECT n.name FROM ((hostbase_host h INNER JOIN hostbase_interface i ON h.id = i.host_id)
        INNER JOIN hostbase_ip p ON i.id = p.interface_id) INNER JOIN hostbase_name n ON p.id = n.ip_id
        WHERE netgroup=\"win\" AND n.only=1 AND h.status = 'active'
        """)
        winmachines.__add__(list(cursor.fetchall()))
        hostslpdfile = header
        for machine in redmachines:
            hostslpdfile += machine[0] + "\n"
        hostslpdfile += "\n"
        for machine in winmachines:
            hostslpdfile += machine[0] + "\n"
        self.filedata['hosts.lpd'] = hostslpdfile
        self.Entries['ConfigFile']['/mcs/etc/hosts.lpd'] = self.FetchFile


    def buildNetgroups(self):
        """Makes the *-machine files"""
        header = """###################################################################
        #  This file lists hosts in the '%s' machine netgroup, it is
        #  automatically generated. DO NOT EDIT THIS FILE! To update
        #  the hosts in this file, edit hostbase and do a 'make nets'
        #  in /mcs/adm/hostbase.
        #
        #  Number of hosts in '%s' machine netgroup: %i
        #\n\n"""

        cursor = connection.cursor()
        # fetches all the hosts that with valid netgroup entries
        cursor.execute("""
        SELECT h.hostname, n.name, h.netgroup, n.only FROM ((hostbase_host h
        INNER JOIN hostbase_interface i ON h.id = i.host_id)
        INNER JOIN hostbase_ip p ON i.id = p.interface_id)
        INNER JOIN hostbase_name n ON p.id = n.ip_id
        WHERE h.netgroup <> '' AND h.netgroup <> 'none' AND h.status = 'active'
        ORDER BY h.netgroup, h.hostname
        """)
        nameslist = cursor.fetchall()
        # gets the first host and initializes the hash
        hostdata = nameslist[0]
        netgroups = {hostdata[2]:[hostdata[0]]}
        for row in nameslist:
            # if new netgroup, create it
            if row[2] not in netgroups:
                netgroups.update({row[2]:[]})
            # if it belongs in the netgroup and has multiple interfaces, put them in
            if hostdata[0] == row[0] and row[3]:
                netgroups[row[2]].append(row[1])
                hostdata = row
            # if its a new host, write the old one to the hash
            elif hostdata[0] != row[0]:
                netgroups[row[2]].append(row[0])
                hostdata = row

        for netgroup in netgroups:
            fileoutput = header % (netgroup, netgroup, len(netgroups[netgroup]))
            for each in netgroups[netgroup]:
                fileoutput += each + "\n"
            self.filedata['%s-machines' % netgroup] = fileoutput
            self.Entries['ConfigFile']['%s-machines' % netgroup] = self.FetchFile
