"""
This file provides the Hostbase plugin.
It manages dns/dhcp/nis host information
"""

from lxml.etree import Element, SubElement
import os
import re
from time import strftime
os.environ['DJANGO_SETTINGS_MODULE'] = 'Bcfg2.Server.Hostbase.settings'
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugin import PluginExecutionError, PluginInitError
from django.template import Context, loader
from django.db import connection
# Compatibility imports
from Bcfg2.Compat import StringIO

try:
    set
except NameError:
    # deprecated since python 2.6
    from sets import Set as set


class Hostbase(Bcfg2.Server.Plugin.Plugin,
               Bcfg2.Server.Plugin.Structure,
               Bcfg2.Server.Plugin.Generator):
    """The Hostbase plugin handles host/network info."""
    name = 'Hostbase'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    filepath = '/my/adm/hostbase/files/bind'
    deprecated = True

    def __init__(self, core, datastore):

        self.ready = False
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Structure.__init__(self)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        files = ['zone.tmpl',
                 'reversesoa.tmpl',
                 'named.tmpl',
                 'reverseappend.tmpl',
                 'dhcpd.tmpl',
                 'hosts.tmpl',
                 'hostsappend.tmpl']
        self.filedata = {}
        self.dnsservers = []
        self.dhcpservers = []
        self.templates = {'zone': loader.get_template('zone.tmpl'),
                          'reversesoa': loader.get_template('reversesoa.tmpl'),
                          'named': loader.get_template('named.tmpl'),
                          'namedviews': loader.get_template('namedviews.tmpl'),
                          'reverseapp': loader.get_template('reverseappend.tmpl'),
                          'dhcp': loader.get_template('dhcpd.tmpl'),
                          'hosts': loader.get_template('hosts.tmpl'),
                          'hostsapp': loader.get_template('hostsappend.tmpl'),
                          }
        self.Entries['ConfigFile'] = {}
        self.__rmi__ = ['rebuildState']
        try:
            self.rebuildState(None)
        except:
            raise PluginInitError

    def FetchFile(self, entry, metadata):
        """Return prebuilt file data."""
        fname = entry.get('name').split('/')[-1]
        if not fname in self.filedata:
            raise PluginExecutionError
        perms = {'owner': 'root',
                 'group': 'root',
                 'mode': '644'}
        [entry.attrib.__setitem__(key, value)
         for (key, value) in list(perms.items())]
        entry.text = self.filedata[fname]

    def BuildStructures(self, metadata):
        """Build hostbase bundle."""
        if metadata.hostname not in self.dnsservers or metadata.hostname not in self.dhcpservers:
            return []
        output = Element("Bundle", name='hostbase')
        if metadata.hostname in self.dnsservers:
            for configfile in self.Entries['ConfigFile']:
                if re.search('/etc/bind/', configfile):
                    SubElement(output, "ConfigFile", name=configfile)
        if metadata.hostname in self.dhcpservers:
            SubElement(output, "ConfigFile", name="/etc/dhcp3/dhcpd.conf")
        return [output]

    def rebuildState(self, _):
        """Pre-cache all state information for hostbase config files
        callable as an XMLRPC function.

        """
        self.buildZones()
        self.buildDHCP()
        self.buildHosts()
        self.buildHostsLPD()
        self.buildPrinters()
        self.buildNetgroups()
        return True

    def buildZones(self):
        """Pre-build and stash zone files."""
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

        cursor.execute("SELECT * FROM hostbase_zone WHERE zone NOT LIKE \'%%.rev\'")
        zones = cursor.fetchall()

        iplist = []
        hosts = {}

        for zone in zones:
            zonefile = StringIO()
            externalzonefile = StringIO()
            cursor.execute("""SELECT n.name FROM hostbase_zone_nameservers z
            INNER JOIN hostbase_nameserver n ON z.nameserver_id = n.id
            WHERE z.zone_id = \'%s\'""" % zone[0])
            nameservers = cursor.fetchall()
            cursor.execute("""SELECT i.ip_addr FROM hostbase_zone_addresses z
            INNER JOIN hostbase_zoneaddress i ON z.zoneaddress_id = i.id
            WHERE z.zone_id = \'%s\'""" % zone[0])
            addresses = cursor.fetchall()
            cursor.execute("""SELECT m.priority, m.mx FROM hostbase_zone_mxs z
            INNER JOIN hostbase_mx m ON z.mx_id = m.id
            WHERE z.zone_id = \'%s\'""" % zone[0])
            mxs = cursor.fetchall()
            context = Context({
                'zone': zone,
                'nameservers': nameservers,
                'addresses': addresses,
                'mxs': mxs
                })
            zonefile.write(self.templates['zone'].render(context))
            externalzonefile.write(self.templates['zone'].render(context))

            querystring = """SELECT h.hostname, p.ip_addr,
            n.name, c.cname, m.priority, m.mx, n.dns_view
            FROM (((((hostbase_host h INNER JOIN hostbase_interface i ON h.id = i.host_id)
            INNER JOIN hostbase_ip p ON i.id = p.interface_id)
            INNER JOIN hostbase_name n ON p.id = n.ip_id)
            INNER JOIN hostbase_name_mxs x ON n.id = x.name_id)
            INNER JOIN hostbase_mx m ON m.id = x.mx_id)
            LEFT JOIN hostbase_cname c ON n.id = c.name_id
            WHERE n.name LIKE '%%%%%s'
            AND h.status = 'active'
            ORDER BY h.hostname, n.name, p.ip_addr
            """ % zone[1]
            cursor.execute(querystring)
            zonehosts = cursor.fetchall()
            prevhost = (None, None, None, None)
            cnames = StringIO()
            cnamesexternal = StringIO()
            for host in zonehosts:
                if not host[2].split(".", 1)[1] == zone[1]:
                    zonefile.write(cnames.getvalue())
                    externalzonefile.write(cnamesexternal.getvalue())
                    cnames = StringIO()
                    cnamesexternal = StringIO()
                    continue
                if not prevhost[1] == host[1] or not prevhost[2] == host[2]:
                    zonefile.write(cnames.getvalue())
                    externalzonefile.write(cnamesexternal.getvalue())
                    cnames = StringIO()
                    cnamesexternal = StringIO()
                    zonefile.write("%-32s%-10s%-32s\n" %
                                   (host[2].split(".", 1)[0], 'A', host[1]))
                    zonefile.write("%-32s%-10s%-3s%s.\n" %
                                   ('', 'MX', host[4], host[5]))
                    if host[6] == 'global':
                        externalzonefile.write("%-32s%-10s%-32s\n" %
                                               (host[2].split(".", 1)[0], 'A', host[1]))
                        externalzonefile.write("%-32s%-10s%-3s%s.\n" %
                                               ('', 'MX', host[4], host[5]))
                elif not prevhost[5] == host[5]:
                    zonefile.write("%-32s%-10s%-3s%s.\n" %
                                   ('', 'MX', host[4], host[5]))
                    if host[6] == 'global':
                        externalzonefile.write("%-32s%-10s%-3s%s.\n" %
                                         ('', 'MX', host[4], host[5]))

                if host[3]:
                    try:
                        if host[3].split(".", 1)[1] == zone[1]:
                            cnames.write("%-32s%-10s%-32s\n" %
                                         (host[3].split(".", 1)[0],
                                          'CNAME', host[2].split(".", 1)[0]))
                            if host[6] == 'global':
                                cnamesexternal.write("%-32s%-10s%-32s\n" %
                                                     (host[3].split(".", 1)[0],
                                                      'CNAME', host[2].split(".", 1)[0]))
                        else:
                            cnames.write("%-32s%-10s%-32s\n" %
                                         (host[3] + ".",
                                          'CNAME',
                                          host[2].split(".", 1)[0]))
                            if host[6] == 'global':
                                cnamesexternal.write("%-32s%-10s%-32s\n" %
                                                     (host[3] + ".",
                                                      'CNAME',
                                                      host[2].split(".", 1)[0]))

                    except:
                        pass
                prevhost = host
            zonefile.write(cnames.getvalue())
            externalzonefile.write(cnamesexternal.getvalue())
            zonefile.write("\n\n%s" % zone[9])
            externalzonefile.write("\n\n%s" % zone[9])
            self.filedata[zone[1]] = zonefile.getvalue()
            self.filedata[zone[1] + ".external"] = externalzonefile.getvalue()
            zonefile.close()
            externalzonefile.close()
            self.Entries['ConfigFile']["%s/%s" % (self.filepath, zone[1])] = self.FetchFile
            self.Entries['ConfigFile']["%s/%s.external" % (self.filepath, zone[1])] = self.FetchFile

        cursor.execute("SELECT * FROM hostbase_zone WHERE zone LIKE \'%%.rev\' AND zone <> \'.rev\'")
        reversezones = cursor.fetchall()

        reversenames = []
        for reversezone in reversezones:
            cursor.execute("""SELECT n.name FROM hostbase_zone_nameservers z
            INNER JOIN hostbase_nameserver n ON z.nameserver_id = n.id
            WHERE z.zone_id = \'%s\'""" % reversezone[0])
            reverse_nameservers = cursor.fetchall()

            context = Context({
                'inaddr': reversezone[1].rstrip('.rev'),
                'zone': reversezone,
                'nameservers': reverse_nameservers,
                })

            self.filedata[reversezone[1]] = self.templates['reversesoa'].render(context)
            self.filedata[reversezone[1] + '.external'] = self.templates['reversesoa'].render(context)
            self.filedata[reversezone[1]] += reversezone[9]
            self.filedata[reversezone[1] + '.external'] += reversezone[9]

            subnet = reversezone[1].split(".")
            subnet.reverse()
            reversenames.append((reversezone[1].rstrip('.rev'), ".".join(subnet[1:])))

        for filename in reversenames:
            cursor.execute("""
            SELECT DISTINCT h.hostname, p.ip_addr, n.dns_view FROM ((hostbase_host h
            INNER JOIN hostbase_interface i ON h.id = i.host_id)
            INNER JOIN hostbase_ip p ON i.id = p.interface_id)
            INNER JOIN hostbase_name n ON n.ip_id = p.id
            WHERE p.ip_addr LIKE '%s%%%%' AND h.status = 'active' ORDER BY p.ip_addr
            """ % filename[1])
            reversehosts = cursor.fetchall()
            zonefile = StringIO()
            externalzonefile = StringIO()
            if len(filename[0].split(".")) == 2:
                originlist = []
                [originlist.append((".".join([ip[1].split(".")[2], filename[0]]),
                                    ".".join([filename[1], ip[1].split(".")[2]])))
                 for ip in reversehosts
                 if (".".join([ip[1].split(".")[2], filename[0]]),
                     ".".join([filename[1], ip[1].split(".")[2]])) not in originlist]
                for origin in originlist:
                    hosts = [(host[1].split("."), host[0])
                             for host in reversehosts
                             if host[1].rstrip('0123456789').rstrip('.') == origin[1]]
                    hosts_external = [(host[1].split("."), host[0])
                                     for host in reversehosts
                                     if (host[1].rstrip('0123456789').rstrip('.') == origin[1]
                                         and host[2] == 'global')]
                    context = Context({
                        'hosts': hosts,
                        'inaddr': origin[0],
                        'fileorigin': filename[0],
                        })
                    zonefile.write(self.templates['reverseapp'].render(context))
                    context = Context({
                        'hosts': hosts_external,
                        'inaddr': origin[0],
                        'fileorigin': filename[0],
                        })
                    externalzonefile.write(self.templates['reverseapp'].render(context))
            else:
                originlist = [filename[0]]
                hosts = [(host[1].split("."), host[0])
                         for host in reversehosts
                         if (host[1].split("."), host[0]) not in hosts]
                hosts_external = [(host[1].split("."), host[0])
                                  for host in reversehosts
                                  if ((host[1].split("."), host[0]) not in hosts_external
                                  and host[2] == 'global')]
                context = Context({
                    'hosts': hosts,
                    'inaddr': filename[0],
                    'fileorigin': None,
                    })
                zonefile.write(self.templates['reverseapp'].render(context))
                context = Context({
                    'hosts': hosts_external,
                    'inaddr': filename[0],
                    'fileorigin': None,
                    })
                externalzonefile.write(self.templates['reverseapp'].render(context))
            self.filedata['%s.rev' % filename[0]] += zonefile.getvalue()
            self.filedata['%s.rev.external' % filename[0]] += externalzonefile.getvalue()
            zonefile.close()
            externalzonefile.close()
            self.Entries['ConfigFile']['%s/%s.rev' % (self.filepath, filename[0])] = self.FetchFile
            self.Entries['ConfigFile']['%s/%s.rev.external' % (self.filepath, filename[0])] = self.FetchFile

        ## here's where the named.conf file gets written
        context = Context({
            'zones': zones,
            'reverses': reversenames,
            })
        self.filedata['named.conf'] = self.templates['named'].render(context)
        self.Entries['ConfigFile']['/my/adm/hostbase/files/named.conf'] = self.FetchFile
        self.filedata['named.conf.views'] = self.templates['namedviews'].render(context)
        self.Entries['ConfigFile']['/my/adm/hostbase/files/named.conf.views'] = self.FetchFile

    def buildDHCP(self):
        """Pre-build dhcpd.conf and stash in the filedata table."""

        # fetches all the hosts with DHCP == True
        cursor = connection.cursor()
        cursor.execute("""
        SELECT hostname, mac_addr, ip_addr
        FROM (hostbase_host h INNER JOIN hostbase_interface i ON h.id = i.host_id)
        INNER JOIN hostbase_ip ip ON i.id = ip.interface_id
        WHERE i.dhcp=1 AND h.status='active' AND i.mac_addr <> ''
        AND i.mac_addr <> 'float' AND i.mac_addr <> 'unknown'
        ORDER BY h.hostname, i.mac_addr
        """)

        dhcphosts = cursor.fetchall()
        count = 0
        hosts = []
        hostdata = [dhcphosts[0][0], dhcphosts[0][1], dhcphosts[0][2]]
        if len(dhcphosts) > 1:
            for x in range(1, len(dhcphosts)):
                # if an interface has 2 or more ip addresses
                # adds the ip to the current interface
                if hostdata[0].split(".")[0] == dhcphosts[x][0].split(".")[0] and hostdata[1] == dhcphosts[x][1]:
                    hostdata[2] = ", ".join([hostdata[2], dhcphosts[x][2]])
                # if a host has 2 or more interfaces
                # writes the current one and grabs the next
                elif hostdata[0].split(".")[0] == dhcphosts[x][0].split(".")[0]:
                    hosts.append(hostdata)
                    count += 1
                    hostdata = ["-".join([dhcphosts[x][0], str(count)]), dhcphosts[x][1], dhcphosts[x][2]]
                # new host found, writes current data to the template
                else:
                    hosts.append(hostdata)
                    count = 0
                    hostdata = [dhcphosts[x][0], dhcphosts[x][1], dhcphosts[x][2]]
        #makes sure the last of the data gets written out
        if hostdata not in hosts:
            hosts.append(hostdata)

        context = Context({
            'hosts': hosts,
            'numips': len(hosts),
            })

        self.filedata['dhcpd.conf'] = self.templates['dhcp'].render(context)
        self.Entries['ConfigFile']['/my/adm/hostbase/files/dhcpd.conf'] = self.FetchFile

    def buildHosts(self):
        """Pre-build and stash /etc/hosts file."""

        append_data = []

        cursor = connection.cursor()
        cursor.execute("""
        SELECT hostname FROM hostbase_host ORDER BY hostname
        """)
        hostbase = cursor.fetchall()
        domains = [host[0].split(".", 1)[1] for host in hostbase]
        domains_set = set(domains)
        domain_data = [(domain, domains.count(domain)) for domain in domains_set]
        domain_data.sort()

        cursor.execute("""
        SELECT ip_addr FROM hostbase_ip ORDER BY ip_addr
        """)
        ips = cursor.fetchall()
        three_octets = [ip[0].rstrip('0123456789').rstrip('.') \
                        for ip in ips]
        three_octets_set = set(three_octets)
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
            WHERE p.ip_addr LIKE \'%s.%%%%\' AND h.status = 'active'""" % three_octet[0]
            cursor.execute(querystring)
            tosort = list(cursor.fetchall())
            tosort.sort(lambda x, y: cmp(int(x[2].split(".")[-1]), int(y[2].split(".")[-1])))
            append_data.append((three_octet, tuple(tosort)))

        two_octets = [ip.rstrip('0123456789').rstrip('.') for ip in three_octets]
        two_octets_set = set(two_octets)
        two_octets_data = [(octet, two_octets.count(octet))
                           for octet in two_octets_set]
        two_octets_data.sort()

        context = Context({
            'domain_data': domain_data,
            'three_octets_data': three_octets_data,
            'two_octets_data': two_octets_data,
            'three_octets': three_octets,
            'num_ips': len(three_octets),
            })

        self.filedata['hosts'] = self.templates['hosts'].render(context)

        for subnet in append_data:
            ips = []
            simple = True
            namelist = [name.split('.', 1)[0] for name in [subnet[1][0][3]]]
            cnamelist = []
            if subnet[1][0][4]:
                cnamelist.append(subnet[1][0][4].split('.', 1)[0])
                simple = False
            appenddata = subnet[1][0]
            for ip in subnet[1][1:]:
                if appenddata[2] == ip[2]:
                    namelist.append(ip[3].split('.', 1)[0])
                    if ip[4]:
                        cnamelist.append(ip[4].split('.', 1)[0])
                        simple = False
                    appenddata = ip
                else:
                    if appenddata[0] == ip[0]:
                        simple = False
                    ips.append((appenddata[2], appenddata[0], set(namelist),
                                cnamelist, simple, appenddata[1]))
                    appenddata = ip
                    simple = True
                    namelist = [ip[3].split('.', 1)[0]]
                    cnamelist = []
                    if ip[4]:
                        cnamelist.append(ip[4].split('.', 1)[0])
                        simple = False
            ips.append((appenddata[2], appenddata[0], set(namelist),
                        cnamelist, simple, appenddata[1]))
            context = Context({
                'subnet': subnet[0],
                'ips': ips,
                })
            self.filedata['hosts'] += self.templates['hostsapp'].render(context)
        self.Entries['ConfigFile']['/mcs/etc/hosts'] = self.FetchFile

    def buildPrinters(self):
        """The /mcs/etc/printers.data file"""
        header = """#  This file is automatically generated. DO NOT EDIT IT!
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
        self.filedata['printers.data'] = printersfile
        self.Entries['ConfigFile']['/mcs/etc/printers.data'] = self.FetchFile

    def buildHostsLPD(self):
        """Creates the /mcs/etc/hosts.lpd file"""

        # this header needs to be changed to be more generic
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
#  automatically generated. DO NOT EDIT THIS FILE!
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
        netgroups = {hostdata[2]: [hostdata[0]]}
        for row in nameslist:
            # if new netgroup, create it
            if row[2] not in netgroups:
                netgroups.update({row[2]: []})
            # if it belongs in the netgroup and has multiple interfaces, put them in
            if hostdata[0] == row[0] and row[3]:
                netgroups[row[2]].append(row[1])
                hostdata = row
            # if its a new host, write the old one to the hash
            elif hostdata[0] != row[0]:
                netgroups[row[2]].append(row[0])
                hostdata = row

        for netgroup in netgroups:
            fileoutput = StringIO()
            fileoutput.write(header % (netgroup, netgroup, len(netgroups[netgroup])))
            for each in netgroups[netgroup]:
                fileoutput.write(each + "\n")
            self.filedata['%s-machines' % netgroup] = fileoutput.getvalue()
            fileoutput.close()
            self.Entries['ConfigFile']['/my/adm/hostbase/makenets/machines/%s-machines' % netgroup] = self.FetchFile

        cursor.execute("""
        UPDATE hostbase_host SET dirty=0
        """)
