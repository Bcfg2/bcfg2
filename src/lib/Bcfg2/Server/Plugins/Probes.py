import re
import os
import sys
import time
import copy
import operator
import lxml.etree
import Bcfg2.Server
import Bcfg2.Server.Plugin
from Bcfg2.Compat import any, json

try:
    from django.db import models
    has_django = True
except ImportError:
    has_django = False

try:
    import syck as yaml
    has_yaml = True
    yaml_error = yaml.error
except ImportError:
    try:
        import yaml
        yaml_error = yaml.YAMLError
        has_yaml = True
    except ImportError:
        has_yaml = False

if has_django:
    class ProbesDataModel(models.Model,
                          Bcfg2.Server.Plugin.PluginDatabaseModel):
        hostname = models.CharField(max_length=255)
        probe = models.CharField(max_length=255)
        timestamp = models.DateTimeField(auto_now=True)
        data = models.TextField(null=True)

    class ProbesGroupsModel(models.Model,
                            Bcfg2.Server.Plugin.PluginDatabaseModel):
        hostname = models.CharField(max_length=255)
        group = models.CharField(max_length=255)


class ClientProbeDataSet(dict):
    """ dict of probe => [probe data] that records a timestamp for
    each host """
    def __init__(self, *args, **kwargs):
        if "timestamp" in kwargs and kwargs['timestamp'] is not None:
            self.timestamp = kwargs.pop("timestamp")
        else:
            self.timestamp = time.time()
        dict.__init__(self, *args, **kwargs)


class ProbeData(str):
    """ a ProbeData object emulates a str object, but also has .xdata,
    .json, and .yaml properties to provide convenient ways to use
    ProbeData objects as XML, JSON, or YAML data """
    def __new__(cls, data):
        return str.__new__(cls, data)
    
    def __init__(self, data):
        str.__init__(self)
        self._xdata = None
        self._json = None
        self._yaml = None

    @property
    def data(self):
        """ provide backwards compatibility with broken ProbeData
        object in bcfg2 1.2.0 thru 1.2.2 """
        return str(self)
        
    @property
    def xdata(self):
        if self._xdata is None:
            try:
                self._xdata = lxml.etree.XML(self.data,
                                             parser=Bcfg2.Server.XMLParser)
            except lxml.etree.XMLSyntaxError:
                pass
        return self._xdata

    @property
    def json(self):
        if self._json is None:
            try:
                self._json = json.loads(self.data)
            except ValueError:
                pass
        return self._json

    @property
    def yaml(self):
        if self._yaml is None and has_yaml:
            try:
                self._yaml = yaml.load(self.data)
            except yaml_error:
                pass
        return self._yaml


class ProbeSet(Bcfg2.Server.Plugin.EntrySet):
    ignore = re.compile("^(\.#.*|.*~|\\..*\\.(tmp|sw[px])|probed\\.xml)$")
    probename = re.compile("(.*/)?(?P<basename>\S+?)(\.(?P<mode>(?:G\d\d)|H)_\S+)?$")
    bangline = re.compile('^#!\s*(?P<interpreter>.*)$')
    basename_is_regex = True

    def __init__(self, path, fam, encoding, plugin_name):
        self.plugin_name = plugin_name
        Bcfg2.Server.Plugin.EntrySet.__init__(self, '[0-9A-Za-z_\-]+', path,
                                              Bcfg2.Server.Plugin.SpecificData,
                                              encoding)
        fam.AddMonitor(path, self)

    def HandleEvent(self, event):
        if (event.filename != self.path and
            not event.filename.endswith("probed.xml")):
            return self.handle_event(event)

    def get_probe_data(self, metadata):
        ret = []
        build = dict()
        candidates = self.get_matching(metadata)
        candidates.sort(key=operator.attrgetter('specific'))
        for entry in candidates:
            rem = self.probename.match(entry.name)
            pname = rem.group('basename')
            if pname not in build:
                build[pname] = entry

        for (name, entry) in list(build.items()):
            probe = lxml.etree.Element('probe')
            probe.set('name', os.path.basename(name))
            probe.set('source', self.plugin_name)
            probe.text = entry.data
            match = self.bangline.match(entry.data.split('\n')[0])
            if match:
                probe.set('interpreter', match.group('interpreter'))
            else:
                probe.set('interpreter', '/bin/sh')
            ret.append(probe)
        return ret


class Probes(Bcfg2.Server.Plugin.Probing,
             Bcfg2.Server.Plugin.Connector,
             Bcfg2.Server.Plugin.DatabaseBacked):
    """A plugin to gather information from a client machine."""
    name = 'Probes'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Connector.__init__(self)
        Bcfg2.Server.Plugin.Probing.__init__(self)
        Bcfg2.Server.Plugin.DatabaseBacked.__init__(self, core, datastore)

        try:
            self.probes = ProbeSet(self.data, core.fam, core.encoding,
                                   self.name)
        except:
            err = sys.exc_info()[1]
            raise Bcfg2.Server.Plugin.PluginInitError(err)

        self.probedata = dict()
        self.cgroups = dict()
        self.load_data()

    def write_data(self, client):
        """Write probe data out for use with bcfg2-info."""
        if self._use_db:
            return self._write_data_db(client)
        else:
            return self._write_data_xml(client)

    def _write_data_xml(self, _):
        top = lxml.etree.Element("Probed")
        for client, probed in sorted(self.probedata.items()):
            cx = lxml.etree.SubElement(top, 'Client', name=client,
                                       timestamp=str(int(probed.timestamp)))
            for probe in sorted(probed):
                lxml.etree.SubElement(cx, 'Probe', name=probe,
                                      value=str(self.probedata[client][probe]))
            for group in sorted(self.cgroups[client]):
                lxml.etree.SubElement(cx, "Group", name=group)
        try:
            datafile = open(os.path.join(self.data, 'probed.xml'), 'w')
            datafile.write(lxml.etree.tostring(top, xml_declaration=False,
                                               pretty_print='true').decode('UTF-8'))
        except IOError:
            err = sys.exc_info()[1]
            self.logger.error("Failed to write probed.xml: %s" % err)

    def _write_data_db(self, client):
        for probe, data in self.probedata[client.hostname].items():
            pdata = \
                ProbesDataModel.objects.get_or_create(hostname=client.hostname,
                                                      probe=probe)[0]
            if pdata.data != data:
                pdata.data = data
                pdata.save()
        ProbesDataModel.objects.filter(hostname=client.hostname).exclude(probe__in=self.probedata[client.hostname]).delete()

        for group in self.cgroups[client.hostname]:
            try:
                ProbesGroupsModel.objects.get(hostname=client.hostname,
                                              group=group)
            except ProbesGroupsModel.DoesNotExist:
                grp = ProbesGroupsModel(hostname=client.hostname,
                                        group=group)
                grp.save()
        ProbesGroupsModel.objects.filter(hostname=client.hostname).exclude(group__in=self.cgroups[client.hostname]).delete()

    def load_data(self):
        if self._use_db:
            return self._load_data_db()
        else:
            return self._load_data_xml()
            
    def _load_data_xml(self):
        try:
            data = lxml.etree.parse(os.path.join(self.data, 'probed.xml'),
                                    parser=Bcfg2.Server.XMLParser).getroot()
        except:
            err = sys.exc_info()[1]
            self.logger.error("Failed to read file probed.xml: %s" % err)
            return
        self.probedata = {}
        self.cgroups = {}
        for client in data.getchildren():
            self.probedata[client.get('name')] = \
                ClientProbeDataSet(timestamp=client.get("timestamp"))
            self.cgroups[client.get('name')] = []
            for pdata in client:
                if pdata.tag == 'Probe':
                    self.probedata[client.get('name')][pdata.get('name')] = \
                        ProbeData(pdata.get("value"))
                elif pdata.tag == 'Group':
                    self.cgroups[client.get('name')].append(pdata.get('name'))

    def _load_data_db(self):
        self.probedata = {}
        self.cgroups = {}
        for pdata in ProbesDataModel.objects.all():
            if pdata.hostname not in self.probedata:
                self.probedata[pdata.hostname] = \
                    ClientProbeDataSet(timestamp=time.mktime(pdata.timestamp.timetuple()))
            self.probedata[pdata.hostname][pdata.probe] = ProbeData(pdata.data)
        for pgroup in ProbesGroupsModel.objects.all():
            if pgroup.hostname not in self.cgroups:
                self.cgroups[pgroup.hostname] = []
            self.cgroups[pgroup.hostname].append(pgroup.group)

    def GetProbes(self, meta, force=False):
        """Return a set of probes for execution on client."""
        return self.probes.get_probe_data(meta)

    def ReceiveData(self, client, datalist):
        if self.core.metadata_cache_mode in ['cautious', 'aggressive']:
            if client.hostname in self.cgroups:
                olddata = copy.copy(self.cgroups[client.hostname])
            else:
                olddata = []

        self.cgroups[client.hostname] = []
        self.probedata[client.hostname] = ClientProbeDataSet()
        for data in datalist:
            self.ReceiveDataItem(client, data)

        if (self.core.metadata_cache_mode in ['cautious', 'aggressive'] and
            olddata != self.cgroups[client.hostname]):
            self.core.metadata_cache.expire(client.hostname)
        self.write_data(client)

    def ReceiveDataItem(self, client, data):
        """Receive probe results pertaining to client."""
        if client.hostname not in self.cgroups:
            self.cgroups[client.hostname] = []
        if client.hostname not in self.probedata:
            self.probedata[client.hostname] = ClientProbeDataSet()
        if data.text == None:
            self.logger.info("Got null response to probe %s from %s" %
                             (data.get('name'), client.hostname))
            self.probedata[client.hostname].update({data.get('name'):
                                                        ProbeData('')})
            return
        dlines = data.text.split('\n')
        self.logger.debug("%s:probe:%s:%s" %
                          (client.hostname, data.get('name'),
                           [line.strip() for line in dlines]))
        for line in dlines[:]:
            if line.split(':')[0] == 'group':
                newgroup = line.split(':')[1].strip()
                if newgroup not in self.cgroups[client.hostname]:
                    self.cgroups[client.hostname].append(newgroup)
                dlines.remove(line)
        dobj = ProbeData("\n".join(dlines))
        self.probedata[client.hostname].update({data.get('name'): dobj})

    def get_additional_groups(self, meta):
        return self.cgroups.get(meta.hostname, list())

    def get_additional_data(self, meta):
        return self.probedata.get(meta.hostname, ClientProbeDataSet())
