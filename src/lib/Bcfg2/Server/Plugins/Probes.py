""" A plugin to gather information from a client machine """

import re
import os
import sys
import time
import copy
import operator
import lxml.etree
import Bcfg2.Server
import Bcfg2.Server.Plugin

try:
    from django.db import models
    from django.core.exceptions import MultipleObjectsReturned
    HAS_DJANGO = True

    class ProbesDataModel(models.Model,
                          Bcfg2.Server.Plugin.PluginDatabaseModel):
        """ The database model for storing probe data """
        hostname = models.CharField(max_length=255)
        probe = models.CharField(max_length=255)
        timestamp = models.DateTimeField(auto_now=True)
        data = models.TextField(null=True)

    class ProbesGroupsModel(models.Model,
                            Bcfg2.Server.Plugin.PluginDatabaseModel):
        """ The database model for storing probe groups """
        hostname = models.CharField(max_length=255)
        group = models.CharField(max_length=255)
except ImportError:
    HAS_DJANGO = False

try:
    import json
    HAS_JSON = True
except ImportError:
    try:
        import simplejson as json
        HAS_JSON = True
    except ImportError:
        HAS_JSON = False

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class ClientProbeDataSet(dict):
    """ dict of probe => [probe data] that records a timestamp for
    each host """
    def __init__(self, *args, **kwargs):
        if "timestamp" in kwargs and kwargs['timestamp'] is not None:
            self.timestamp = kwargs.pop("timestamp")
        else:
            self.timestamp = time.time()
        dict.__init__(self, *args, **kwargs)


class ProbeData(str):  # pylint: disable=E0012,R0924
    """ a ProbeData object emulates a str object, but also has .xdata,
    .json, and .yaml properties to provide convenient ways to use
    ProbeData objects as XML, JSON, or YAML data """
    def __new__(cls, data):
        return str.__new__(cls, data)

    def __init__(self, data):  # pylint: disable=W0613
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
        """ The probe data as a lxml.etree._Element document """
        if self._xdata is None:
            try:
                self._xdata = lxml.etree.XML(self.data,
                                             parser=Bcfg2.Server.XMLParser)
            except lxml.etree.XMLSyntaxError:
                pass
        return self._xdata

    @property
    def json(self):
        """ The probe data as a decoded JSON data structure """
        if self._json is None and HAS_JSON:
            try:
                self._json = json.loads(self.data)
            except ValueError:
                pass
        return self._json

    @property
    def yaml(self):
        """ The probe data as a decoded YAML data structure """
        if self._yaml is None and HAS_YAML:
            try:
                self._yaml = yaml.load(self.data)
            except yaml.YAMLError:
                pass
        return self._yaml


class ProbeSet(Bcfg2.Server.Plugin.EntrySet):
    """ Handle universal and group- and host-specific probe files """
    ignore = re.compile(r'^(\.#.*|.*~|\..*\.(tmp|sw[px])|probed\.xml)$')
    probename = \
        re.compile(r'(.*/)?(?P<basename>\S+?)(\.(?P<mode>(?:G\d\d)|H)_\S+)?$')
    bangline = re.compile(r'^#!\s*(?P<interpreter>.*)$')
    basename_is_regex = True

    def __init__(self, path, fam, encoding, plugin_name):
        self.plugin_name = plugin_name
        Bcfg2.Server.Plugin.EntrySet.__init__(self, r'[0-9A-Za-z_\-]+', path,
                                              Bcfg2.Server.Plugin.SpecificData,
                                              encoding)
        fam.AddMonitor(path, self)

    def HandleEvent(self, event):
        """ handle events on everything but probed.xml """
        if (event.filename != self.path and
            not event.filename.endswith("probed.xml")):
            return self.handle_event(event)

    def get_probe_data(self, metadata):
        """ Get an XML description of all probes for a client suitable
        for sending to that client.

        :param metadata: The client metadata to get probes for.
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: list of lxml.etree._Element objects, each of which
                  represents one probe.
        """
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
            if (metadata.version_info and
                metadata.version_info > (1, 3, 1, '', 0)):
                try:
                    probe.text = entry.data.decode('utf-8')
                except AttributeError:
                    probe.text = entry.data
            else:
                try:
                    probe.text = entry.data
                except:  # pylint: disable=W0702
                    self.logger.error("Client unable to handle unicode "
                                      "probes. Skipping %s" %
                                      probe.get('name'))
                    continue
            match = self.bangline.match(entry.data.split('\n')[0])
            if match:
                probe.set('interpreter', match.group('interpreter'))
            else:
                probe.set('interpreter', '/bin/sh')
            ret.append(probe)
        return ret

    def __str__(self):
        return "ProbeSet for %s" % self.plugin_name


class Probes(Bcfg2.Server.Plugin.Probing,
             Bcfg2.Server.Plugin.Connector,
             Bcfg2.Server.Plugin.DatabaseBacked):
    """ A plugin to gather information from a client machine """
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Connector.__init__(self)
        Bcfg2.Server.Plugin.Probing.__init__(self)
        Bcfg2.Server.Plugin.DatabaseBacked.__init__(self, core, datastore)

        try:
            self.probes = ProbeSet(self.data, core.fam, core.setup['encoding'],
                                   self.name)
        except:
            err = sys.exc_info()[1]
            raise Bcfg2.Server.Plugin.PluginInitError(err)

        self.probedata = dict()
        self.cgroups = dict()
        self.load_data()
    __init__.__doc__ = Bcfg2.Server.Plugin.DatabaseBacked.__init__.__doc__

    @Bcfg2.Server.Plugin.track_statistics()
    def write_data(self, client):
        """ Write probe data out for use with bcfg2-info """
        if self._use_db:
            return self._write_data_db(client)
        else:
            return self._write_data_xml(client)

    def _write_data_xml(self, _):
        """ Write received probe data to probed.xml """
        top = lxml.etree.Element("Probed")
        for client, probed in sorted(self.probedata.items()):
            # make a copy of probe data for this client in case it
            # submits probe data while we're trying to write
            # probed.xml
            probedata = copy.copy(probed)
            ctag = \
                lxml.etree.SubElement(top, 'Client', name=client,
                                      timestamp=str(int(probedata.timestamp)))
            for probe in sorted(probedata):
                lxml.etree.SubElement(
                    ctag, 'Probe', name=probe,
                    value=self.probedata[client][probe])
            for group in sorted(self.cgroups[client]):
                lxml.etree.SubElement(ctag, "Group", name=group)
        try:
            top.getroottree().write(os.path.join(self.data, 'probed.xml'),
                                    xml_declaration=False,
                                    pretty_print='true')
        except IOError:
            err = sys.exc_info()[1]
            self.logger.error("Failed to write probed.xml: %s" % err)

    @Bcfg2.Server.Plugin.DatabaseBacked.get_db_lock
    def _write_data_db(self, client):
        """ Write received probe data to the database """
        for probe, data in self.probedata[client.hostname].items():
            pdata = \
                ProbesDataModel.objects.get_or_create(hostname=client.hostname,
                                                      probe=probe)[0]
            if pdata.data != data:
                pdata.data = data
                pdata.save()

        ProbesDataModel.objects.filter(
            hostname=client.hostname).exclude(
                probe__in=self.probedata[client.hostname]).delete()

        for group in self.cgroups[client.hostname]:
            try:
                ProbesGroupsModel.objects.get_or_create(
                    hostname=client.hostname,
                    group=group)
            except MultipleObjectsReturned:
                ProbesGroupsModel.objects.filter(hostname=client.hostname,
                                                 group=group).delete()
                ProbesGroupsModel.objects.get_or_create(
                    hostname=client.hostname,
                    group=group)
        ProbesGroupsModel.objects.filter(
            hostname=client.hostname).exclude(
                group__in=self.cgroups[client.hostname]).delete()

    def load_data(self):
        """ Load probe data from the appropriate backend (probed.xml
        or the database) """
        if self._use_db:
            return self._load_data_db()
        else:
            return self._load_data_xml()

    def _load_data_xml(self):
        """ Load probe data from probed.xml """
        try:
            data = lxml.etree.parse(os.path.join(self.data, 'probed.xml'),
                                    parser=Bcfg2.Server.XMLParser).getroot()
        except (IOError, lxml.etree.XMLSyntaxError):
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
        """ Load probe data from the database """
        self.probedata = {}
        self.cgroups = {}
        for pdata in ProbesDataModel.objects.all():
            if pdata.hostname not in self.probedata:
                self.probedata[pdata.hostname] = ClientProbeDataSet(
                    timestamp=time.mktime(pdata.timestamp.timetuple()))
            self.probedata[pdata.hostname][pdata.probe] = ProbeData(pdata.data)
        for pgroup in ProbesGroupsModel.objects.all():
            if pgroup.hostname not in self.cgroups:
                self.cgroups[pgroup.hostname] = []
            self.cgroups[pgroup.hostname].append(pgroup.group)

    @Bcfg2.Server.Plugin.track_statistics()
    def GetProbes(self, meta):
        return self.probes.get_probe_data(meta)
    GetProbes.__doc__ = Bcfg2.Server.Plugin.Probing.GetProbes.__doc__

    @Bcfg2.Server.Plugin.track_statistics()
    def ReceiveData(self, client, datalist):
        if self.core.metadata_cache_mode in ['cautious', 'aggressive']:
            if client.hostname in self.cgroups:
                olddata = copy.copy(self.cgroups[client.hostname])
            else:
                olddata = []

        cgroups = []
        cprobedata = ClientProbeDataSet()
        for data in datalist:
            self.ReceiveDataItem(client, data, cgroups, cprobedata)
        self.cgroups[client.hostname] = cgroups
        self.probedata[client.hostname] = cprobedata

        if (self.core.metadata_cache_mode in ['cautious', 'aggressive'] and
            olddata != self.cgroups[client.hostname]):
            self.core.metadata_cache.expire(client.hostname)
        self.write_data(client)
    ReceiveData.__doc__ = Bcfg2.Server.Plugin.Probing.ReceiveData.__doc__

    def ReceiveDataItem(self, client, data, cgroups, cprobedata):
        """Receive probe results pertaining to client."""
        if data.text is None:
            self.logger.info("Got null response to probe %s from %s" %
                             (data.get('name'), client.hostname))
            cprobedata[data.get('name')] = ProbeData('')
            return
        dlines = data.text.split('\n')
        self.logger.debug("Processing probe from %s: %s:%s" %
                          (client.hostname, data.get('name'),
                           [line.strip() for line in dlines]))
        for line in dlines[:]:
            if line.split(':')[0] == 'group':
                newgroup = line.split(':')[1].strip()
                if newgroup not in cgroups:
                    cgroups.append(newgroup)
                dlines.remove(line)
        dobj = ProbeData("\n".join(dlines))
        cprobedata[data.get('name')] = dobj

    def get_additional_groups(self, meta):
        return self.cgroups.get(meta.hostname, list())
    get_additional_groups.__doc__ = \
        Bcfg2.Server.Plugin.Connector.get_additional_groups.__doc__

    def get_additional_data(self, meta):
        return self.probedata.get(meta.hostname, ClientProbeDataSet())
    get_additional_data.__doc__ = \
        Bcfg2.Server.Plugin.Connector.get_additional_data.__doc__
