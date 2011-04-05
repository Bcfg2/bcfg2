'''This module implements a Nagios configuration generator'''

import glob
import logging
import lxml.etree
import os
import re
import socket

import Bcfg2.Server.Plugin

LOGGER = logging.getLogger('Bcfg2.Plugins.NagiosGen')

host_config_fmt = \
'''
define host{
        host_name       %s
        alias           %s
        address         %s
'''


class NagiosGen(Bcfg2.Server.Plugin.Plugin,
                Bcfg2.Server.Plugin.Generator):
    """NagiosGen is a Bcfg2 plugin that dynamically generates
       Nagios configuration file based on Bcfg2 data.
    """
    name = 'NagiosGen'
    __version__ = '0.6'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        self.Entries = {'Path':
                {'/etc/nagiosgen.status': self.createhostconfig,
                '/etc/nagios/nagiosgen.cfg': self.createserverconfig}}

        self.client_attrib = {'encoding': 'ascii',
                              'owner': 'root',
                              'group': 'root',
                              'type': 'file',
                              'perms': '0400'}
        self.server_attrib = {'encoding': 'ascii',
                              'owner': 'nagios',
                              'group': 'nagios',
                              'type': 'file',
                              'perms': '0440'}

    def getparents(self, hostname):
        """Return parents for given hostname."""
        depends = []
        if not os.path.isfile('%s/parents.xml' % (self.data)):
            return depends

        tree = lxml.etree.parse('%s/parents.xml' % (self.data))
        for entry in tree.findall('.//Depend'):
            if entry.attrib['name'] == hostname:
                depends.append(entry.attrib['on'])
        return depends

    def createhostconfig(self, entry, metadata):
        """Build host specific configuration file."""
        host_address = socket.gethostbyname(metadata.hostname)
        host_groups = [grp for grp in metadata.groups if \
                       os.path.isfile('%s/%s-group.cfg' % (self.data, grp))]
        host_config = host_config_fmt % \
                      (metadata.hostname, metadata.hostname, host_address)

        if host_groups:
            host_config += '        hostgroups      %s\n' % (",".join(host_groups))

        xtra = None
        if hasattr(metadata, 'Properties') and \
                'NagiosGen.xml' in metadata.Properties:
            for q in (metadata.hostname, 'default'):
                xtra = metadata.Properties['NagiosGen.xml'].data.find(q)
                if xtra is not None:
                    break

        if xtra is not None:
            directives = list(xtra)
            for item in directives:
                host_config += '        %-32s %s\n' % (item.tag, item.text)

        else:
            host_config += '        use             default\n'

        host_config += '}\n'
        entry.text = host_config
        [entry.attrib.__setitem__(key, value) for \
            (key, value) in list(self.client_attrib.items())]
        try:
            fileh = open("%s/%s-host.cfg" % \
                        (self.data, metadata.hostname), 'w')
            fileh.write(host_config)
            fileh.close()
        except OSError, ioerr:
            LOGGER.error("Failed to write %s/%s-host.cfg" % \
                        (self.data, metadata.hostname))
            LOGGER.error(ioerr)

    def createserverconfig(self, entry, _):
        """Build monolithic server configuration file."""
        host_configs = glob.glob('%s/*-host.cfg' % self.data)
        group_configs = glob.glob('%s/*-group.cfg' % self.data)
        host_data = ""
        group_data = ""
        for host in host_configs:
            hostfile = open(host, 'r')
            hostname = host.split('/')[-1].replace('-host.cfg', '')
            parents = self.getparents(hostname)
            if parents:
                hostlines = hostfile.readlines()
            else:
                hostdata = hostfile.read()
            hostfile.close()

            if parents:
                hostdata = ''
                addparents = True
                for line in hostlines:
                    line = line.replace('\n', '')
                    if 'parents' in line:
                        line += ',' + ','.join(parents)
                        addparents = False
                    if '}' in line:
                        line = ''
                    hostdata += "%s\n" % line
                if addparents:
                    hostdata += "        parents         %s\n" % ','.join(parents)
                hostdata += "}\n"

            host_data += hostdata
        for group in group_configs:
            group_name = re.sub("(-group.cfg|.*/(?=[^/]+))", "", group)
            if host_data.find(group_name) != -1:
                groupfile = open(group, 'r')
                group_data += groupfile.read()
                groupfile.close()
        entry.text = group_data + host_data
        [entry.attrib.__setitem__(key, value) for \
            (key, value) in list(self.server_attrib.items())]
        try:
            fileh = open("%s/nagiosgen.cfg" % (self.data), 'w')
            fileh.write(group_data + host_data)
            fileh.close()
        except OSError, ioerr:
            LOGGER.error("Failed to write %s/nagiosgen.cfg" % (self.data))
            LOGGER.error(ioerr)
