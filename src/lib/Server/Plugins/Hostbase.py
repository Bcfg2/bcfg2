'''This file provides the Hostbase plugin. It manages dns/dhcp/nis host information'''
__revision__ = '$Revision$'

from syslog import syslog, LOG_INFO
from cElementTree import XML
from Cheetah.Template import Template
from Bcfg2.Server.Plugin import Plugin, PluginExecutionError, PluginInitError, DirectoryBacked

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
                syslog(LOG_INFO, "%s:Got event for unexpected file %s" % (self.__name__, event.filename))
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
        files = ['dnsdata.xml', 'hostbase.xml', 'networks.xml']
        Plugin.__init__(self, core, datastore)
        try:
            DataNexus.__init__(self, datastore + '/Hostbase/data',
                               files, self.core.fam)
        except:
            self.LogError("Failed to load data directory")
            raise PluginInitError
        self.xdata = {}
        self.filedata = {}
        self.zonetempl = Template(open(self.data + '/templates/' + 'zonetemplate.tmpl').read())
        self.reversesoa = Template(open(self.data + '/templates/' + 'reversesoa.tmpl').read())
        self.named = Template(open(self.data + '/templates/' + 'namedtemplate.tmpl').read())
        self.reverseappend = Template(open(self.data + '/templates/' + 'reverseappend.tmpl').read())
        self.dhcptmpl = Template(open(self.data + '/templates/' + 'dhcpd_template.tmpl').read())
        self.Entries['ConfigFile'] = {}

    def FetchFile(self, entry, metadata):
        fname = entry.get('name').split('/')[-1]
        if not self.filedata.has_key(fname):
            raise PluginExecutionError
        entry.attrib.update({'owner':'root', 'group':'root', 'perms':'644'})
        entry.text = self.filedata[fname]

    def rebuildState(self, event):
        '''Pre-cache all state information for hostbase config files'''
        if self.entries.has_key(event.filename) and not self.xdata.has_key(event.filename):
            self.xdata[event.filename] = XML(self.entries[event.filename].data)
        if [item for item in self.files if not self.entries.has_key(item)]:
            return
        # we might be able to rebuild data more sparsely,
        # but hostbase.xml is the only one that will really change often
        # rebuild zoneinfo
        iplist = []
        for zone in self.xdata['dnsdata.xml']:
            zonehosts = []
            for host in [host for host in self.xdata['hostbase.xml']
                         if host.get('domain') == zone.get('domain')]:
                hostname = host.get('hostname')
                if zone.get('domain') == 'mcs.anl.gov':
                    ## special cases for the mcs.anl.gov domain
                    ## all machines have a "-eth" entry as well as an entry identifying their subnet
                    ## they also have their mail exchangers after every address
                    ipnodes = host.findall("interface/ip")
                    zonehosts.append((hostname, ipnodes[0].attrib['ip'], ipnodes[0].findall("name/mx"), None))
                    [zonehosts.append(("-".join([hostname, ipnode.attrib['dnssuffix']]), \
                                       ipnode.attrib['ip'], ipnode.findall("name/mx"), None))
                     for ipnode in ipnodes]
                    [zonehosts.append(("-".join([hostname, namenode.attrib['name']]), \
                                       ipnode.attrib['ip'], namenode.findall("mx"), None))
                     for ipnode in ipnodes
                     for namenode in ipnode
                     if namenode.attrib['name'] != ""]
                else:
                    ipnodes = host.findall("interface/ip")
                    zonehosts.append((host.attrib['hostname'], ipnodes[0].attrib['ip'], None, None))
                    [zonehosts.append(("-".join([host.attrib['hostname'], namenode.attrib['name']]), ipnode.attrib['ip'], None, None))
                     for ipnode in ipnodes
                     for namenode in ipnode
                     if namenode.attrib['name'] != ""]

                [zonehosts.append((host.attrib['hostname'], None, None, cnamenode.attrib['cname']))
                 for cnamenode in host.findall("interface/ip/name/cname")
                 if cnamenode.attrib['cname'] != ""]

                [iplist.append(ipnode.attrib['ip']) for ipnode in host.findall("interface/ip")]
            zonehosts.sort()
            self.zonetempl.zone = zone
            self.zonetempl.root = self.xdata['dnsdata.xml']
            self.zonetempl.hosts = zonehosts
            self.filedata[zone.get('domain')] = str(self.zonetempl)
        # now all zone forward files are built
        iplist.sort()
        filelist = []
        temp = None
        for x in range(len(iplist)-1):
            addressparts = iplist[x].split(".")
            if addressparts[:3] != iplist[x+1].split(".")[:3] and addressparts[:2] == iplist[x+1].split(".")[:2] \
            and ".".join([addressparts[1], addressparts[0]]) not in filelist:
                filelist.append(".".join([addressparts[1], addressparts[0]]))
            elif addressparts[:3] != iplist[x+1].split(".")[:3] and \
            addressparts[:2] != iplist[x+1].split(".")[:2] and \
            ".".join([addressparts[1], addressparts[0]]) not in filelist:
                filelist.append(".".join([addressparts[2], addressparts[1], addressparts[0]]))
            if x+1 == len(iplist) - 1:
                temp = iplist[x+1].split(".")
                if ".".join([temp[2], temp[1], temp[0]]) not in filelist \
                and ".".join([temp[1], temp[0]]) not in filelist:
                    filelist.append(".".join([temp[2], temp[1], temp[0]]))

        for filename in filelist:
            self.reversesoa.inaddr = filename
            self.reversesoa.zone = zone
            self.reversesoa.root = self.xdata['dnsdata.xml']
            self.filedata["%s.rev" % filename] = str(self.reversesoa)

        self.named.zones = self.xdata['dnsdata.xml']
        self.named.reverses = filelist
        self.filedata["named.conf"] = str(self.named)

        for filename in filelist:
            originlist = []
            towrite = filename.split(".")
            towrite.reverse()
            if len(towrite) > 2:
                self.reverseappend.hosts = [(ipnode.get('ip').split('.'), host.get('hostname'),
                                             host.get('domain'), ipnode.get('num'), ipnode.get('dnssuffix'))
                                            for host in self.xdata['hostbase.xml']
                                            for ipnode in host.findall('interface/ip')
                                            if ipnode.get('ip').split('.')[:3] == towrite]
                
                self.reverseappend.inaddr = filename
                self.reverseappend.fileorigin = None
                self.filedata["%s.rev" % filename] += str(self.reverseappend)
            else:
                revhosts = [(ipnode.get('ip').split('.'), host.get('hostname'), host.get('domain'),
                             ipnode.get('num'), ipnode.get('dnssuffix')) 
                            for host in self.xdata['hostbase.xml']
                            for ipnode in host.findall("interface/ip")
                            if ipnode.get('ip').split(".")[:2] == towrite]

                [originlist.append(".".join([reversehost[0][2], reversehost[0][1], reversehost[0][0]]))
                 for reversehost in revhosts
                 if ".".join([reversehost[0][2], reversehost[0][1], reversehost[0][0]]) not in originlist]

                revhosts.sort()
                originlist.sort()
                for origin in originlist:
                    outputlist = [rhost for rhost in revhosts
                     if ".".join([rhost[0][2], rhost[0][1], rhost[0][0]]) == origin] 
                    self.reverseappend.fileorigin = filename
                    self.reverseappend.hosts = outputlist
                    self.reverseappend.inaddr = origin
                    self.filedata["%s.rev" % filename] += str(self.reverseappend)
        self.buildDHCP()
        for key in self.filedata:
            self.Entries['ConfigFile']["%s/%s" % (self.filepath, key)] = self.FetchFile

    def buildDHCP(self):
        '''Pre-build dhcpd.conf and stash in the filedata table'''
        if 'networks.xml' not in self.xdata.keys():
            print "not running before networks is cached"
            return
        networkroot = self.xdata['networks.xml']
        if 'hostbase.xml' not in self.xdata.keys():
            print "not running before hostbase is cached"
            return
        hostbase = self.xdata['hostbase.xml']
        vlanandsublist = []
        subnets = networkroot.findall("subnet")
        for vlan in networkroot.findall("vlan"):
            vlansubs = vlan.findall("subnet")
            vlansubs.sort(lambda x, y: cmp(x.get("address"), y.get("address")))
            vlanandsublist.append((vlan, vlansubs))

        subnets140 = [subnet for subnet in subnets if subnet.attrib['address'].split(".")[0] == "140"]
        privatesubnets = [subnet for subnet in subnets if subnet.attrib['address'].split(".")[0] != "140"]
        subnets140.sort(lambda x, y: cmp(x.get("address"), y.get("address")))
        privatesubnets.sort(lambda x, y: cmp(x.get("address"), y.get("address")))

        dhcphosts = [host for host in hostbase if host.get('dhcp') == 'y' \
                     and host.find("interface").get('mac') != 'float' \
                     and host.find("interface").get('mac') != ""]

        hosts = []
        for host in dhcphosts:
            if len(host.findall("interface")) == 1 and len(host.findall("interface/ip")) == 1:
                hosts.append([host.get('hostname'), host.get('domain'), \
                              host.find("interface").get('mac'), \
                              host.find("interface/ip").get('ip')])
            elif len(host.findall("interface")) > 1:
                count = 0
                for interface in host.findall("interface"):
                    if count == 0 and interface.find("ip") is not None:
                        hostdata = [host.get('hostname'), host.get('domain'), \
                                    interface.get('mac'), interface.find("ip").get('ip')]
                    elif count != 0 and interface.find("ip") is not None:
                        hostdata = [host.get('hostname'), "-".join([host.get('domain'), str(count)]), \
                                    interface.get('mac'), interface.find("ip").get('ip')]
                    if len(interface.findall("ip")) > 1:
                        for ipnode in interface.findall("ip")[1:]:
                            hostdata[3] = ", ".join([hostdata[3], ipnode.get('ip')])
                    count += 1
                    hosts.append(hostdata)

        hosts.sort(lambda x, y: cmp(x[0], y[0]))
        self.dhcptmpl.hosts = hosts
        self.dhcptmpl.privatesubnets = privatesubnets
        self.dhcptmpl.subnets140 = subnets140
        self.dhcptmpl.vlans = vlanandsublist
        self.dhcptmpl.networkroot = networkroot
        self.filedata['/etc/dhcpd.conf'] = str(self.dhcptmpl)
