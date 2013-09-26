""" Query tags from AWS via boto, optionally setting group membership """

import os
import re
import sys
import Bcfg2.Server.Lint
import Bcfg2.Server.Plugin
from boto import connect_ec2
from Bcfg2.Cache import Cache
from Bcfg2.Compat import ConfigParser


class NoInstanceFound(Exception):
    """ Raised when there's no AWS instance for a given hostname """


class AWSTagPattern(object):
    """ Handler for a single Tag entry """

    def __init__(self, name, value, groups):
        self.name = re.compile(name)
        if value is not None:
            self.value = re.compile(value)
        else:
            self.value = value
        self.groups = groups

    def get_groups(self, tags):
        """ Get groups that apply to the given tag set """
        for key, value in tags.items():
            name_match = self.name.search(key)
            if name_match:
                if self.value is not None:
                    value_match = self.value.search(value)
                    if value_match:
                        return self._munge_groups(value_match)
                else:
                    return self._munge_groups(name_match)
                break
        return []

    def _munge_groups(self, match):
        """ Replace backreferences (``$1``, ``$2``) in Group tags with
        their values in the regex. """
        rv = []
        sub = match.groups()
        for group in self.groups:
            newg = group
            for idx in range(len(sub)):
                newg = newg.replace('$%s' % (idx + 1), sub[idx])
            rv.append(newg)
        return rv

    def __str__(self):
        if self.value:
            return "%s: %s=%s: %s" % (self.__class__.__name__, self.name,
                                      self.value, self.groups)
        else:
            return "%s: %s: %s" % (self.__class__.__name__, self.name,
                                   self.groups)


class PatternFile(Bcfg2.Server.Plugin.XMLFileBacked):
    """ representation of AWSTags config.xml """
    __identifier__ = None
    create = 'AWSTags'

    def __init__(self, filename, core=None):
        try:
            fam = core.fam
        except AttributeError:
            fam = None
        Bcfg2.Server.Plugin.XMLFileBacked.__init__(self, filename, fam=fam,
                                                   should_monitor=True)
        self.core = core
        self.tags = []

    def Index(self):
        Bcfg2.Server.Plugin.XMLFileBacked.Index(self)
        if (self.core and
            self.core.metadata_cache_mode in ['cautious', 'aggressive']):
            self.core.metadata_cache.expire()
        self.tags = []
        for entry in self.xdata.xpath('//Tag'):
            try:
                groups = [g.text for g in entry.findall('Group')]
                self.tags.append(AWSTagPattern(entry.get("name"),
                                               entry.get("value"),
                                               groups))
            except:  # pylint: disable=W0702
                self.logger.error("AWSTags: Failed to initialize pattern %s: "
                                  "%s" % (entry.get("name"),
                                          sys.exc_info()[1]))

    def get_groups(self, hostname, tags):
        """ return a list of groups that should be added to the given
        client based on patterns that match the hostname """
        ret = []
        for pattern in self.tags:
            try:
                ret.extend(pattern.get_groups(tags))
            except:  # pylint: disable=W0702
                self.logger.error("AWSTags: Failed to process pattern %s for "
                                  "%s" % (pattern, hostname),
                                  exc_info=1)
        return ret


class AWSTags(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.Caching,
              Bcfg2.Server.Plugin.ClientRunHooks,
              Bcfg2.Server.Plugin.Connector):
    """ Query tags from AWS via boto, optionally setting group membership """
    __rmi__ = Bcfg2.Server.Plugin.Plugin.__rmi__ + ['expire_cache']

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Caching.__init__(self)
        Bcfg2.Server.Plugin.ClientRunHooks.__init__(self)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        try:
            key_id = self.core.setup.cfp.get("awstags", "access_key_id")
            secret_key = self.core.setup.cfp.get("awstags",
                                                 "secret_access_key")
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            err = sys.exc_info()[1]
            raise Bcfg2.Server.Plugin.PluginInitError(
                "AWSTags is not configured in bcfg2.conf: %s" % err)
        self.debug_log("%s: Connecting to EC2" % self.name)
        self._ec2 = connect_ec2(aws_access_key_id=key_id,
                                aws_secret_access_key=secret_key)
        self._tagcache = Cache()
        try:
            self._keep_cache = self.core.setup.cfp.getboolean("awstags",
                                                              "cache")
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            self._keep_cache = True

        self.config = PatternFile(os.path.join(self.data, 'config.xml'),
                                  core=core)

    def _load_instance(self, hostname):
        """ Load an instance from EC2 whose private DNS name matches
        the given hostname """
        self.debug_log("AWSTags: Loading instance with private-dns-name=%s" %
                       hostname)
        filters = {'private-dns-name': hostname}
        reservations = self._ec2.get_all_instances(filters=filters)
        if reservations:
            res = reservations[0]
            if res.instances:
                return res.instances[0]
        raise NoInstanceFound(
            "AWSTags: No instance found with private-dns-name=%s" %
            hostname)

    def _get_tags_from_ec2(self, hostname):
        """ Get tags for the given host from EC2. This does not use
        the local caching layer. """
        self.debug_log("AWSTags: Getting tags for %s from AWS" %
                       hostname)
        try:
            return self._load_instance(hostname).tags
        except NoInstanceFound:
            self.debug_log(sys.exc_info()[1])
            return dict()

    def get_tags(self, metadata):
        """ Get tags for the given host.  This caches the tags locally
        if 'cache' in the ``[awstags]`` section of ``bcfg2.conf`` is
        true. """
        if not self._keep_cache:
            return self._get_tags_from_ec2(metadata)

        if metadata.hostname not in self._tagcache:
            self._tagcache[metadata.hostname] = \
                self._get_tags_from_ec2(metadata.hostname)
        return self._tagcache[metadata.hostname]

    def expire_cache(self, key=None):
        self._tagcache.expire(key=key)

    def start_client_run(self, metadata):
        self.expire_cache(key=metadata.hostname)

    def get_additional_data(self, metadata):
        return self.get_tags(metadata)

    def get_additional_groups(self, metadata):
        return self.config.get_groups(metadata.hostname,
                                      self.get_tags(metadata))


class AWSTagsLint(Bcfg2.Server.Lint.ServerPlugin):
    """ ``bcfg2-lint`` plugin to check all given :ref:`AWSTags
    <server-plugins-connectors-awstags>` patterns for validity. """

    def Run(self):
        cfg = self.core.plugins['AWSTags'].config
        for entry in cfg.xdata.xpath('//Tag'):
            self.check(entry, "name")
            if entry.get("value"):
                self.check(entry, "value")

    @classmethod
    def Errors(cls):
        return {"pattern-fails-to-initialize": "error"}

    def check(self, entry, attr):
        """ Check a single attribute (``name`` or ``value``) of a
        single entry for validity. """
        try:
            re.compile(entry.get(attr))
        except re.error:
            self.LintError("pattern-fails-to-initialize",
                           "'%s' regex could not be compiled: %s\n    %s" %
                           (attr, sys.exc_info()[1], entry.get("name")))
