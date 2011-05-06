'''This module implements a Nagios configuration generator'''

import os
import re
import sys
import glob
import socket
import logging
import lxml.etree

import Bcfg2.Server.Plugin

LOGGER = logging.getLogger('Bcfg2.Plugins.NagiosGen')

line_fmt = '\t%-32s %s'

class NagiosGenConfig(Bcfg2.Server.Plugin.SingleXMLFileBacked,
                      Bcfg2.Server.Plugin.StructFile):
    def __init__(self, filename, fam):
        Bcfg2.Server.Plugin.SingleXMLFileBacked.__init__(self, filename, fam)
        Bcfg2.Server.Plugin.StructFile.__init__(self, filename)

    
class NagiosGen(Bcfg2.Server.Plugin.Plugin,
                Bcfg2.Server.Plugin.Generator):
    """NagiosGen is a Bcfg2 plugin that dynamically generates
       Nagios configuration file based on Bcfg2 data.
    """
    name = 'NagiosGen'
    __version__ = '0.7'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        self.config = NagiosGenConfig(os.path.join(self.data, 'config.xml'),
                                      core.fam)
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

    def createhostconfig(self, entry, metadata):
        """Build host specific configuration file."""
        host_address = socket.gethostbyname(metadata.hostname)
        host_groups = [grp for grp in metadata.groups
                       if os.path.isfile('%s/%s-group.cfg' % (self.data, grp))]
        host_config = ['define host {',
                       line_fmt % ('host_name', metadata.hostname),
                       line_fmt % ('alias', metadata.hostname),
                       line_fmt % ('address', host_address)]

        if host_groups:
            host_config.append(line_fmt % ("hostgroups",
                                           ",".join(host_groups)))

        # read the old-style Properties config, but emit a warning.
        xtra = dict()
        props = None
        if (hasattr(metadata, 'Properties') and
            'NagiosGen.xml' in metadata.Properties):
            props = metadata.Properties['NagiosGen.xml'].data
        if props is not None:
            LOGGER.warn("Parsing deprecated Properties/NagiosGen.xml. "
                        "Update to the new-style config with "
                        "nagiosgen-convert.py.")
            xtra = dict((el.tag, el.text)
                        for el in props.find(metadata.hostname))
            # hold off on parsing the defaults until we've checked for
            # a new-style config

        # read the old-style parents.xml, but emit a warning
        pfile = os.path.join(self.data, "parents.xml")
        if os.path.exists(pfile):
            LOGGER.warn("Parsing deprecated NagiosGen/parents.xml. "
                        "Update to the new-style config with "
                        "nagiosgen-convert.py.")
            parents = lxml.etree.parse(pfile)
            for el in parents.xpath("//Depend[@name='%s']" % metadata.hostname):
                if 'parent' in xtra:
                    xtra['parent'] += "," + el.get("on")
                else:
                    xtra['parent'] = el.get("on")

        # read the new-style config and overwrite the old-style config
        for el in self.config.Match(metadata):
            if el.tag == 'Option':
                xtra[el.get("name")] = el.text

        # if we haven't found anything in the new- or old-style
        # configs, finally read defaults from old-style config
        if not xtra and props is not None:
            xtra = dict((el.tag, el.text) for el in props.find('default'))

        if xtra:
            host_config.extend([line_fmt % (opt, val)
                                for opt, val in list(xtra.items())])
        else:
            host_config.append(line_fmt % ('use', 'default'))

        host_config.append('}')
        entry.text = "%s\n" % "\n".join(host_config)
        [entry.attrib.__setitem__(key, value)
         for (key, value) in list(self.client_attrib.items())]
        try:
            fileh = open("%s/%s-host.cfg" %
                         (self.data, metadata.hostname), 'w')
            fileh.write(entry.text)
            fileh.close()
        except OSError:
            ioerr = sys.exc_info()[1]
            LOGGER.error("Failed to write %s/%s-host.cfg" %
                         (self.data, metadata.hostname))
            LOGGER.error(ioerr)

    def createserverconfig(self, entry, _):
        """Build monolithic server configuration file."""
        host_configs = glob.glob('%s/*-host.cfg' % self.data)
        group_configs = glob.glob('%s/*-group.cfg' % self.data)
        host_data = []
        group_data = []
        for host in host_configs:
            host_data.append(open(host, 'r').read())
            
        for group in group_configs:
            group_name = re.sub("(-group.cfg|.*/(?=[^/]+))", "", group)
            if "\n".join(host_data).find(group_name) != -1:
                groupfile = open(group, 'r')
                group_data.append(groupfile.read())
                groupfile.close()
        
        entry.text = "%s\n\n%s" % ("\n".join(group_data), "\n".join(host_data))
        [entry.attrib.__setitem__(key, value)
         for (key, value) in list(self.server_attrib.items())]
        try:
            fileh = open("%s/nagiosgen.cfg" % self.data, 'w')
            fileh.write(entry.text)
            fileh.close()
        except OSError:
            ioerr = sys.exc_info()[1]
            LOGGER.error("Failed to write %s/nagiosgen.cfg" % self.data)
            LOGGER.error(ioerr)
