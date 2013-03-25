'''This module implements a Nagios configuration generator'''

import os
import re
import sys
import glob
import socket
import Bcfg2.Server
import Bcfg2.Server.Plugin


class NagiosGen(Bcfg2.Server.Plugin.Plugin,
                Bcfg2.Server.Plugin.Generator):
    """ NagiosGen is a Bcfg2 plugin that dynamically generates Nagios
    configuration file based on Bcfg2 data. """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    line_fmt = '\t%-32s %s'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        self.config = \
            Bcfg2.Server.Plugin.StructFile(os.path.join(self.data,
                                                        'config.xml'),
                                           core.fam, should_monitor=True,
                                           create=self.name)
        self.Entries = {'Path':
                        {'/etc/nagiosgen.status': self.createhostconfig,
                         '/etc/nagios/nagiosgen.cfg': self.createserverconfig}}

        self.client_attrib = {'encoding': 'ascii',
                              'owner': 'root',
                              'group': 'root',
                              'type': 'file',
                              'mode': '0400'}
        self.server_attrib = {'encoding': 'ascii',
                              'owner': 'nagios',
                              'group': 'nagios',
                              'type': 'file',
                              'mode': '0440'}

    def createhostconfig(self, entry, metadata):
        """Build host specific configuration file."""
        try:
            host_address = socket.gethostbyname(metadata.hostname)
        except socket.gaierror:
            self.logger.error("Failed to find IP address for %s" %
                              metadata.hostname)
            raise Bcfg2.Server.Plugin.PluginExecutionError
        host_groups = [grp for grp in metadata.groups
                       if os.path.isfile('%s/%s-group.cfg' % (self.data, grp))]
        host_config = ['define host {',
                       self.line_fmt % ('host_name', metadata.hostname),
                       self.line_fmt % ('alias', metadata.hostname),
                       self.line_fmt % ('address', host_address)]

        if host_groups:
            host_config.append(self.line_fmt % ("hostgroups",
                                                ",".join(host_groups)))

        # read the config
        xtra = dict()
        for el in self.config.Match(metadata):
            if el.tag == 'Option':
                xtra[el.get("name")] = el.text

        if xtra:
            host_config.extend([self.line_fmt % (opt, val)
                                for opt, val in list(xtra.items())])
        if 'use' not in xtra:
            host_config.append(self.line_fmt % ('use', 'default'))

        host_config.append('}')
        entry.text = "%s\n" % "\n".join(host_config)
        for (key, value) in list(self.client_attrib.items()):
            entry.attrib.__setitem__(key, value)
        fname = os.path.join(self.data, metadata.hostname + "-host.cfg")
        try:
            open(fname, 'w').write(entry.text)
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error("Failed to write %s: %s" % (fname, err))

    def createserverconfig(self, entry, _):
        """Build monolithic server configuration file."""
        host_configs = glob.glob(os.path.join(self.data, '*-host.cfg'))
        group_configs = glob.glob(os.path.join(self.data, '*-group.cfg'))
        host_data = []
        group_data = []
        for host in host_configs:
            host_data.append(open(host, 'r').read())

        group_list = []
        for line in "\n".join(host_data).splitlines():
            # only include those groups which are actually used
            if "hostgroup" in line:
                group_list += line.split()[1].split(',')

        group_list = list(set(group_list))

        for group in group_configs:
            group_name = re.sub("(-group.cfg|.*/(?=[^/]+))", "", group)
            if group_name in group_list:
                groupfile = open(group, 'r')
                group_data.append(groupfile.read())
                groupfile.close()

        entry.text = "%s\n\n%s" % ("\n".join(group_data), "\n".join(host_data))
        for (key, value) in list(self.server_attrib.items()):
            entry.attrib.__setitem__(key, value)
        fname = os.path.join(self.data, "nagiosgen.cfg")
        try:
            open(fname, 'w').write(entry.text)
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error("Failed to write %s: %s" % (fname, err))
