import time
import lxml.etree
import operator
import re

try:
    import json
    has_json = True
except ImportError:
    try:
        import simplejson as json
        has_json = True
    except ImportError:
        has_json = False

try:
    import syck
    has_syck = True
except ImportError:
    has_syck = False
    try:
        import yaml
        has_yaml = True
    except ImportError:
        has_yaml = False

import Bcfg2.Server.Plugin

specific_probe_matcher = re.compile("(.*/)?(?P<basename>\S+)(.(?P<mode>[GH](\d\d)?)_\S+)")
probe_matcher = re.compile("(.*/)?(?P<basename>\S+)")

class ClientProbeDataSet(dict):
    """ dict of probe => [probe data] that records a for each host """
    def __init__(self, *args, **kwargs):
        if "timestamp" in kwargs and kwargs['timestamp'] is not None:
            self.timestamp = kwargs.pop("timestamp")
        else:
            self.timestamp = time.time()
        dict.__init__(self, *args, **kwargs)


class ProbeData(object):
    """ a ProbeData object emulates a str object, but also has .xdata
    and .json properties to provide convenient ways to use ProbeData
    objects as XML or JSON data """
    def __init__(self, data):
        self.data = data
        self._xdata = None
        self._json = None
        self._yaml = None

    def __str__(self):
        return str(self.data)
    
    def __repr__(self):
        return repr(self.data)
    
    def __getattr__(self, name):
        """ make ProbeData act like a str object """
        return getattr(self.data, name)

    def __complex__(self):
        return complex(self.data)

    def __int__(self):
        return int(self.data)

    def __long__(self):
        return long(self.data)

    def __float__(self):
        return float(self.data)

    def __eq__(self, other):
        return str(self) == str(other)

    def __ne__(self, other):
        return str(self) != str(other)

    def __gt__(self, other):
        return str(self) > str(other)

    def __lt__(self, other):
        return str(self) < str(other)

    def __ge__(self, other):
        return self > other or self == other

    def __le__(self, other):
        return self < other or self == other

    @property
    def xdata(self):
        if self._xdata is None:
            try:
                self._xdata = lxml.etree.XML(self.data)
            except lxml.etree.XMLSyntaxError:
                pass
        return self._xdata

    @property
    def json(self):
        if self._json is None and has_json:
            try:
                self._json = json.loads(self.data)
            except ValueError:
                pass
        return self._json

    @property
    def yaml(self):
        if self._yaml is None:
            if has_yaml:
                try:
                    self._yaml = yaml.load(self.data)
                except yaml.YAMLError:
                    pass
            elif has_syck:
                try:
                    self._yaml = syck.load(self.data)
                except syck.error:
                    pass
        return self._yaml


class ProbeSet(Bcfg2.Server.Plugin.EntrySet):
    ignore = re.compile("^(\.#.*|.*~|\\..*\\.(tmp|sw[px])|probed\\.xml)$")

    def __init__(self, path, fam, encoding, plugin_name):
        fpattern = '[0-9A-Za-z_\-]+'
        self.plugin_name = plugin_name
        Bcfg2.Server.Plugin.EntrySet.__init__(self, fpattern, path,
                                              Bcfg2.Server.Plugin.SpecificData,
                                              encoding)
        fam.AddMonitor(path, self)
        self.bangline = re.compile('^#!(?P<interpreter>.*)$')

    def HandleEvent(self, event):
        if event.filename != self.path:
            return self.handle_event(event)

    def get_probe_data(self, metadata):
        ret = []
        build = dict()
        candidates = self.get_matching(metadata)
        candidates.sort(key=operator.attrgetter('specific'))
        for entry in candidates:
            rem = specific_probe_matcher.match(entry.name)
            if not rem:
                rem = probe_matcher.match(entry.name)
            pname = rem.group('basename')
            if pname not in build:
                build[pname] = entry

        for (name, entry) in list(build.items()):
            probe = lxml.etree.Element('probe')
            probe.set('name', name.split('/')[-1])
            probe.set('source', self.plugin_name)
            probe.text = entry.data
            match = self.bangline.match(entry.data.split('\n')[0])
            if match:
                probe.set('interpreter', match.group('interpreter'))
            else:
                probe.set('interpreter', '/bin/sh')
            ret.append(probe)
        return ret


class Probes(Bcfg2.Server.Plugin.Plugin,
             Bcfg2.Server.Plugin.Probing,
             Bcfg2.Server.Plugin.Connector):
    """A plugin to gather information from a client machine."""
    name = 'Probes'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        Bcfg2.Server.Plugin.Probing.__init__(self)

        try:
            self.probes = ProbeSet(self.data, core.fam, core.encoding,
                                   self.name)
        except:
            raise Bcfg2.Server.Plugin.PluginInitError

        self.probedata = dict()
        self.cgroups = dict()
        self.load_data()

    def write_data(self):
        """Write probe data out for use with bcfg2-info."""
        top = lxml.etree.Element("Probed")
        for client, probed in sorted(self.probedata.items()):
            cx = lxml.etree.SubElement(top, 'Client', name=client,
                                       timestamp=str(int(probed.timestamp)))
            for probe in sorted(probed):
                lxml.etree.SubElement(cx, 'Probe', name=probe,
                                      value=str(self.probedata[client][probe]))
            for group in sorted(self.cgroups[client]):
                lxml.etree.SubElement(cx, "Group", name=group)
        data = lxml.etree.tostring(top, encoding='UTF-8',
                                   xml_declaration=True,
                                   pretty_print='true')
        try:
            datafile = open("%s/%s" % (self.data, 'probed.xml'), 'w')
        except IOError:
            self.logger.error("Failed to write probed.xml")
        datafile.write(data.decode('utf-8'))

    def load_data(self):
        try:
            data = lxml.etree.parse(self.data + '/probed.xml').getroot()
        except:
            self.logger.error("Failed to read file probed.xml")
            return
        self.probedata = {}
        self.cgroups = {}
        for client in data.getchildren():
            self.probedata[client.get('name')] = \
                ClientProbeDataSet(timestamp=client.get("timestamp"))
            self.cgroups[client.get('name')] = []
            for pdata in client:
                if (pdata.tag == 'Probe'):
                    self.probedata[client.get('name')][pdata.get('name')] = \
                        ProbeData(pdata.get('value'))
                elif (pdata.tag == 'Group'):
                    self.cgroups[client.get('name')].append(pdata.get('name'))

    def GetProbes(self, meta, force=False):
        """Return a set of probes for execution on client."""
        return self.probes.get_probe_data(meta)

    def ReceiveData(self, client, datalist):
        self.cgroups[client.hostname] = []
        self.probedata[client.hostname] = ClientProbeDataSet()
        for data in datalist:
            self.ReceiveDataItem(client, data)
        self.write_data()

    def ReceiveDataItem(self, client, data):
        """Receive probe results pertaining to client."""
        if client.hostname not in self.cgroups:
            self.cgroups[client.hostname] = []
        if data.text == None:
            self.logger.error("Got null response to probe %s from %s" % \
                              (data.get('name'), client.hostname))
            try:
                self.probedata[client.hostname].update({data.get('name'):
                                                        ProbeData('')})
            except KeyError:
                self.probedata[client.hostname] = \
                    ClientProbeDataSet([(data.get('name'), ProbeData(''))])
            return
        dlines = data.text.split('\n')
        self.logger.debug("%s:probe:%s:%s" % (client.hostname,
            data.get('name'), [line.strip() for line in dlines]))
        for line in dlines[:]:
            if line.split(':')[0] == 'group':
                newgroup = line.split(':')[1].strip()
                if newgroup not in self.cgroups[client.hostname]:
                    self.cgroups[client.hostname].append(newgroup)
                dlines.remove(line)
        dobj = ProbeData("\n".join(dlines))
        try:
            self.probedata[client.hostname].update({data.get('name'): dobj})
        except KeyError:
            self.probedata[client.hostname] = \
                ClientProbeDataSet([(data.get('name'), dobj)])

    def get_additional_groups(self, meta):
        return self.cgroups.get(meta.hostname, list())

    def get_additional_data(self, meta):
        return self.probedata.get(meta.hostname, ClientProbeDataSet())
