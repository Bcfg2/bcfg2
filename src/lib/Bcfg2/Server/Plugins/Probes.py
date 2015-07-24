""" A plugin to gather information from a client machine """

import re
import os
import sys
import time
import copy
import operator
import lxml.etree
import Bcfg2.Server
import Bcfg2.Server.Cache
import Bcfg2.Server.Plugin
from Bcfg2.Compat import unicode, any  # pylint: disable=W0622
import Bcfg2.Server.FileMonitor
from Bcfg2.Logger import Debuggable
from Bcfg2.Server.Statistics import track_statistics

HAS_DJANGO = False
# pylint: disable=C0103
ProbesDataModel = None
ProbesGroupsModel = None
# pylint: enable=C0103


def load_django_models():
    """ Load models for Django after option parsing has completed """
    # pylint: disable=W0602
    global ProbesDataModel, ProbesGroupsModel, HAS_DJANGO
    # pylint: enable=W0602
    try:
        from django.db import models
        HAS_DJANGO = True
    except ImportError:
        HAS_DJANGO = False
        return

    class ProbesDataModel(models.Model,  # pylint: disable=W0621,W0612
                          Bcfg2.Server.Plugin.PluginDatabaseModel):
        """ The database model for storing probe data """
        hostname = models.CharField(max_length=255)
        probe = models.CharField(max_length=255)
        timestamp = models.DateTimeField(auto_now=True)
        data = models.TextField(null=True)

    class ProbesGroupsModel(models.Model,  # pylint: disable=W0621,W0612
                            Bcfg2.Server.Plugin.PluginDatabaseModel):
        """ The database model for storing probe groups """
        hostname = models.CharField(max_length=255)
        group = models.CharField(max_length=255)


try:
    import json
    # py2.4 json library is structured differently
    json.loads  # pylint: disable=W0104
    HAS_JSON = True
except (ImportError, AttributeError):
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


class ProbeStore(Debuggable):
    """ Caching abstraction layer between persistent probe data
    storage and the Probes plugin."""

    def __init__(self, core, datadir):  # pylint: disable=W0613
        Debuggable.__init__(self)
        self.core = core
        self._groupcache = Bcfg2.Server.Cache.Cache("Probes", "probegroups")
        self._datacache = Bcfg2.Server.Cache.Cache("Probes", "probedata")

    def get_groups(self, hostname):
        """ Get the list of groups for the given host """
        if hostname not in self._groupcache:
            self._load_groups(hostname)
        return self._groupcache.get(hostname, [])

    def set_groups(self, hostname, groups):
        """ Set the list of groups for the given host """
        raise NotImplementedError

    def get_data(self, hostname):
        """ Get a dict of probe data for the given host """
        if hostname not in self._datacache:
            self._load_data(hostname)
        return self._datacache.get(hostname, dict())

    def set_data(self, hostname, data):
        """ Set probe data for the given host """
        raise NotImplementedError

    def _load_groups(self, hostname):
        """ When probe groups are not found in the cache, this
        function is called to load them from the backend (XML or
        database). """
        raise NotImplementedError

    def _load_data(self, hostname):
        """ When probe groups are not found in the cache, this
        function is called to load them from the backend (XML or
        database). """
        raise NotImplementedError

    def commit(self):
        """ Commit the current data in the cache to the persistent
        backend store. This is not used with the
        :class:`Bcfg2.Server.Plugins.Probes.DBProbeStore`, because it
        commits on every change. """
        pass


class DBProbeStore(ProbeStore, Bcfg2.Server.Plugin.DatabaseBacked):
    """ Caching abstraction layer between the database and the Probes
    plugin. """
    create = False

    def __init__(self, core, datadir):
        Bcfg2.Server.Plugin.DatabaseBacked.__init__(self, core)
        ProbeStore.__init__(self, core, datadir)

    @property
    def _use_db(self):
        return True

    def _load_groups(self, hostname):
        Bcfg2.Server.Cache.expire("Probes", "probegroups", hostname)
        groupdata = ProbesGroupsModel.objects.filter(hostname=hostname)
        self._groupcache[hostname] = list(set(r.group for r in groupdata))
        self.core.metadata_cache.expire(hostname)

    @Bcfg2.Server.Plugin.DatabaseBacked.get_db_lock
    def set_groups(self, hostname, groups):
        Bcfg2.Server.Cache.expire("Probes", "probegroups", hostname)
        olddata = self._groupcache.get(hostname, [])
        self._groupcache[hostname] = groups
        for group in groups:
            try:
                ProbesGroupsModel.objects.get_or_create(
                    hostname=hostname,
                    group=group)
            except ProbesGroupsModel.MultipleObjectsReturned:
                ProbesGroupsModel.objects.filter(hostname=hostname,
                                                 group=group).delete()
                ProbesGroupsModel.objects.get_or_create(
                    hostname=hostname,
                    group=group)
        ProbesGroupsModel.objects.filter(
            hostname=hostname).exclude(group__in=groups).delete()
        if olddata != groups:
            self.core.metadata_cache.expire(hostname)

    def _load_data(self, hostname):
        Bcfg2.Server.Cache.expire("Probes", "probegroups", hostname)
        Bcfg2.Server.Cache.expire("Probes", "probedata", hostname)
        self._datacache[hostname] = ClientProbeDataSet()
        ts_set = False
        for pdata in ProbesDataModel.objects.filter(hostname=hostname):
            if not ts_set:
                self._datacache[hostname].timestamp = \
                    time.mktime(pdata.timestamp.timetuple())
                ts_set = True
            self._datacache[hostname][pdata.probe] = ProbeData(pdata.data)
        self.core.metadata_cache.expire(hostname)

    @Bcfg2.Server.Plugin.DatabaseBacked.get_db_lock
    def set_data(self, hostname, data):
        Bcfg2.Server.Cache.expire("Probes", "probedata", hostname)
        self._datacache[hostname] = ClientProbeDataSet()
        expire_metadata = False
        for probe, pdata in data.items():
            self._datacache[hostname][probe] = pdata
            try:
                record, created = ProbesDataModel.objects.get_or_create(
                    hostname=hostname,
                    probe=probe)
            except ProbesDataModel.MultipleObjectsReturned:
                ProbesDataModel.objects.filter(hostname=hostname,
                                               probe=probe).delete()
                record, created = ProbesDataModel.objects.get_or_create(
                    hostname=hostname,
                    probe=probe)
            expire_metadata |= created
            if record.data != pdata:
                record.data = pdata
                record.save()
                expire_metadata = True
        qset = ProbesDataModel.objects.filter(
            hostname=hostname).exclude(probe__in=data.keys())
        if len(qset):
            qset.delete()
            expire_metadata = True
        if expire_metadata:
            self.core.metadata_cache.expire(hostname)


class XMLProbeStore(ProbeStore):
    """ Caching abstraction layer between ``probed.xml`` and the
    Probes plugin."""
    def __init__(self, core, datadir):
        ProbeStore.__init__(self, core, datadir)
        self._fname = os.path.join(datadir, 'probed.xml')
        self._load_data()

    def _load_data(self, _=None):
        """ Load probe data from probed.xml """
        Bcfg2.Server.Cache.expire("Probes", "probegroups")
        Bcfg2.Server.Cache.expire("Probes", "probedata")
        if not os.path.exists(self._fname):
            self.commit()
        try:
            data = lxml.etree.parse(self._fname,
                                    parser=Bcfg2.Server.XMLParser).getroot()
        except (IOError, lxml.etree.XMLSyntaxError):
            err = sys.exc_info()[1]
            self.logger.error("Failed to read file probed.xml: %s" % err)
            return
        for client in data.getchildren():
            self._datacache[client.get('name')] = \
                ClientProbeDataSet(timestamp=client.get("timestamp"))
            self._groupcache[client.get('name')] = []
            for pdata in client:
                if pdata.tag == 'Probe':
                    self._datacache[client.get('name')][pdata.get('name')] = \
                        ProbeData(pdata.get("value"))
                elif pdata.tag == 'Group':
                    self._groupcache[client.get('name')].append(
                        pdata.get('name'))

        self.core.metadata_cache.expire()

    def _load_groups(self, hostname):
        self._load_data(hostname)

    def commit(self):
        """ Write received probe data to probed.xml """
        top = lxml.etree.Element("Probed")
        for client, probed in sorted(self._datacache.items()):
            # make a copy of probe data for this client in case it
            # submits probe data while we're trying to write
            # probed.xml
            probedata = copy.copy(probed)
            ctag = \
                lxml.etree.SubElement(top, 'Client', name=client,
                                      timestamp=str(int(probedata.timestamp)))
            for probe in sorted(probedata):
                try:
                    lxml.etree.SubElement(
                        ctag, 'Probe', name=probe,
                        value=self._datacache[client][probe].decode('utf-8'))
                except AttributeError:
                    lxml.etree.SubElement(
                        ctag, 'Probe', name=probe,
                        value=self._datacache[client][probe])
            for group in sorted(self._groupcache[client]):
                lxml.etree.SubElement(ctag, "Group", name=group)
        try:
            top.getroottree().write(self._fname,
                                    xml_declaration=False,
                                    pretty_print='true')
        except IOError:
            err = sys.exc_info()[1]
            self.logger.error("Failed to write %s: %s" % (self._fname, err))

    def set_groups(self, hostname, groups):
        Bcfg2.Server.Cache.expire("Probes", "probegroups", hostname)
        olddata = self._groupcache.get(hostname, [])
        self._groupcache[hostname] = groups
        if olddata != groups:
            self.core.metadata_cache.expire(hostname)

    def set_data(self, hostname, data):
        Bcfg2.Server.Cache.expire("Probes", "probedata", hostname)
        self._datacache[hostname] = ClientProbeDataSet()
        expire_metadata = False
        for probe, pdata in data.items():
            olddata = self._datacache[hostname].get(probe, ProbeData(''))
            self._datacache[hostname][probe] = pdata
            expire_metadata |= olddata != data
        if expire_metadata:
            self.core.metadata_cache.expire(hostname)


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
        if isinstance(data, unicode):
            return str.__new__(cls, data.encode('utf-8'))
        else:
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

    def __init__(self, path, plugin_name):
        self.plugin_name = plugin_name
        Bcfg2.Server.Plugin.EntrySet.__init__(self, r'[0-9A-Za-z_\-]+', path,
                                              Bcfg2.Server.Plugin.SpecificData)
        Bcfg2.Server.FileMonitor.get_fam().AddMonitor(path, self)

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
                except ValueError:
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

    groupline_re = re.compile(r'^group:\s*(?P<groupname>\S+)\s*')

    options = [
        Bcfg2.Options.BooleanOption(
            cf=('probes', 'use_database'), dest="probes_db",
            help="Use database capabilities of the Probes plugin"),
        Bcfg2.Options.Option(
            cf=('probes', 'allowed_groups'), dest="probes_allowed_groups",
            help="Whitespace-separated list of group name regexps to which "
            "probes can assign a client",
            default=[re.compile('.*')],
            type=Bcfg2.Options.Types.anchored_regex_list)]
    options_parsed_hook = staticmethod(load_django_models)

    def __init__(self, core):
        Bcfg2.Server.Plugin.Probing.__init__(self)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        Bcfg2.Server.Plugin.DatabaseBacked.__init__(self, core)

        self.probes = ProbeSet(self.data, self.name)
        if self._use_db:
            self.probestore = DBProbeStore(core, self.data)
        else:
            self.probestore = XMLProbeStore(core, self.data)

    @track_statistics()
    def GetProbes(self, metadata):
        return self.probes.get_probe_data(metadata)

    def ReceiveData(self, client, datalist):
        cgroups = set()
        cdata = dict()
        for data in datalist:
            groups, cdata[data.get("name")] = \
                self.ReceiveDataItem(client, data)
            cgroups.update(groups)
        self.probestore.set_groups(client.hostname, list(cgroups))
        self.probestore.set_data(client.hostname, cdata)
        self.probestore.commit()

    def ReceiveDataItem(self, client, data):
        """ Receive probe results pertaining to client.  Returns a
        tuple of (<probe groups>, <probe data>). """
        if data.text is None:
            self.logger.info("Got null response to probe %s from %s" %
                             (data.get('name'), client.hostname))
            return [], ''
        dlines = data.text.split('\n')
        self.logger.debug("Processing probe from %s: %s:%s" %
                          (client.hostname, data.get('name'),
                           [line.strip() for line in dlines]))
        groups = []
        for line in dlines[:]:
            match = self.groupline_re.match(line)
            if match:
                newgroup = match.group("groupname")
                if self._group_allowed(newgroup):
                    groups.append(newgroup)
                else:
                    self.logger.warning(
                        "Disallowed group assignment %s from %s" %
                        (newgroup, client.hostname))
                dlines.remove(line)
        return (groups, ProbeData("\n".join(dlines)))

    def get_additional_groups(self, metadata):
        return self.probestore.get_groups(metadata.hostname)

    def get_additional_data(self, metadata):
        return self.probestore.get_data(metadata.hostname)

    def _group_allowed(self, group):
        """ Determine if the named group can be set as a probe group
        by checking the regexes listed in the [probes] groups_allowed
        setting """
        return any(r.match(group)
                   for r in Bcfg2.Options.setup.probes_allowed_groups)
