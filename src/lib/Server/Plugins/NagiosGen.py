'''This module implements a Nagios configuration generator'''

import glob
import logging
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
    '''NagiosGen is a Bcfg2 plugin that dynamically generates
       Nagios configuration file based on Bcfg2 data.'''
    name = 'NagiosGen'
    __version__ = '0.6'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        self.Entries = {'ConfigFile':
                {'/etc/nagiosgen.status'   : self.createhostconfig,
                '/etc/nagios/nagiosgen.cfg': self.createserverconfig}}

        self.client_attrib = {'encoding': 'ascii', 'owner':'root', \
                         'group':'root', 'perms':'0400'}
        self.server_attrib = {'encoding': 'ascii', 'owner':'nagios', \
                         'group':'nagios', 'perms':'0440'}

    def createhostconfig(self, entry, metadata):
        '''Build host specific configuration file'''
        host_address = socket.gethostbyname(metadata.hostname)
        host_groups = [grp for grp in metadata.groups if \
                       os.path.isfile('%s/%s-group.cfg' % (self.data, grp))]
        host_config = host_config_fmt % \
                      (metadata.hostname, metadata.hostname, host_address)

        if host_groups:
            host_config += '        hostgroups      %s\n' % (",".join(host_groups))

        if hasattr(metadata, 'Properties') and  \
               'NagiosGen.xml' in metadata.Properties and \
               metadata.Properties['NagiosGen.xml'].data.find(metadata.hostname) \
               is not None:
            directives = list(metadata.Properties['NagiosGen.xml'].data.find(metadata.hostname))
            for item in directives:
                host_config += '        %-32s %s\n' % (item.tag, item.text)

        else:
            host_config += '        use             default\n'

        host_config += '}\n'
        entry.text = host_config
        [entry.attrib.__setitem__(key, value) for \
            (key, value) in self.client_attrib.iteritems()]
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
        '''Build monolithic server configuration file'''
        host_configs  = glob.glob('%s/*-host.cfg' % self.data)
        group_configs = glob.glob('%s/*-group.cfg' % self.data)
        host_data = ""
        group_data = ""
        for host in host_configs:
            hostfile = open(host, 'r')
            host_data += hostfile.read()
            hostfile.close()
        for group in group_configs:
            group_name = re.sub("(-group.cfg|.*/(?=[^/]+))", "", group)
            if host_data.find(group_name) != -1:
                groupfile = open(group, 'r')
                group_data += groupfile.read()
                groupfile.close()
        entry.text = group_data + host_data
        [entry.attrib.__setitem__(key, value) for \
            (key, value) in self.server_attrib.iteritems()]
        try:
            fileh = open("%s/nagiosgen.cfg" % (self.data), 'w')
            fileh.write(group_data + host_data)
            fileh.close()
        except OSError, ioerr:
            LOGGER.error("Failed to write %s/nagiosgen.cfg" % (self.data))
            LOGGER.error(ioerr)
