""" A plugin to run Puppet external node classifiers """

import os
import sys
import Bcfg2.Server
import Bcfg2.Server.Plugin
from Bcfg2.Utils import Executor

try:
    from syck import load as yaml_load, error as yaml_error
except ImportError:
    try:
        from yaml import load as yaml_load, YAMLError as yaml_error
    except ImportError:
        raise ImportError("No yaml library could be found")


class PuppetENCFile(Bcfg2.Server.Plugin.FileBacked):
    """ A representation of a Puppet external node classifier script """

    def HandleEvent(self, event=None):
        return


class PuppetENC(Bcfg2.Server.Plugin.Plugin,
                Bcfg2.Server.Plugin.Connector,
                Bcfg2.Server.Plugin.ClientRunHooks,
                Bcfg2.Server.Plugin.DirectoryBacked):
    """ A plugin to run Puppet external node classifiers
    (http://docs.puppetlabs.com/guides/external_nodes.html) """
    __child__ = PuppetENCFile

    def __init__(self, core):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        Bcfg2.Server.Plugin.ClientRunHooks.__init__(self)
        Bcfg2.Server.Plugin.DirectoryBacked.__init__(self, self.data)
        self.cache = dict()
        self.cmd = Executor()

    def _run_encs(self, metadata):
        """ Run all Puppet ENCs """
        cache = dict(groups=[], params=dict())
        for enc in self.entries.keys():
            epath = os.path.join(self.data, enc)
            self.debug_log("PuppetENC: Running ENC %s for %s" %
                           (enc, metadata.hostname))
            result = self.cmd.run([epath, metadata.hostname])
            if not result.success:
                msg = "PuppetENC: Error running ENC %s for %s: %s" % \
                    (enc, metadata.hostname, result.error)
                self.logger.error(msg)
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
            if result.stderr:
                self.debug_log("ENC Error: %s" % result.stderr)

            try:
                yaml = yaml_load(result.stdout)
                self.debug_log("Loaded data from %s for %s: %s" %
                               (enc, metadata.hostname, yaml))
            except yaml_error:
                err = sys.exc_info()[1]
                msg = "Error decoding YAML from %s for %s: %s" % \
                    (enc, metadata.hostname, err)
                self.logger.error(msg)
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)

            groups = yaml.get("classes", yaml.get("groups", dict()))
            if groups:
                if isinstance(groups, list):
                    self.debug_log("ENC %s adding groups to %s: %s" %
                                   (enc, metadata.hostname, groups))
                    cache['groups'].extend(groups)
                else:
                    self.debug_log("ENC %s adding groups to %s: %s" %
                                   (enc, metadata.hostname, groups.keys()))
                    for group, params in groups.items():
                        cache['groups'].append(group)
                        if params:
                            cache['params'].update(params)
            if "parameters" in yaml and yaml['parameters']:
                cache['params'].update(yaml['parameters'])
            if "environment" in yaml:
                self.logger.info("Ignoring unsupported environment section of "
                                 "ENC %s for %s" % (enc, metadata.hostname))

        self.cache[metadata.hostname] = cache

    def get_additional_groups(self, metadata):
        if metadata.hostname not in self.cache:
            self._run_encs(metadata)
        return self.cache[metadata.hostname]['groups']

    def get_additional_data(self, metadata):
        if metadata.hostname not in self.cache:
            self._run_encs(metadata)
        return self.cache[metadata.hostname]['params']

    def end_client_run(self, metadata):
        """ clear the entire cache at the end of each client run. this
        guarantees that each client will run all ENCs at or near the
        start of each run; we have to clear the entire cache instead
        of just the cache for this client because a client that builds
        templates that use metadata for other clients will populate
        the cache for those clients, which we don't want. This makes
        the caching less than stellar, but it does prevent multiple
        runs of ENCs for a single host a) for groups and data
        separately; and b) when a single client's metadata is
        generated multiple times by separate templates """
        self.cache = dict()
        if self.core.metadata_cache_mode == 'aggressive':
            # clear the metadata client cache if we're in aggressive
            # mode, and produce a warning.  PuppetENC really isn't
            # compatible with aggressive mode, since we don't know
            # when the output from a given ENC has changed, and thus
            # can't invalidate the cache sanely.
            self.logger.warning("PuppetENC is incompatible with aggressive "
                                "client metadata caching, try 'cautious' or "
                                "'initial' instead")
            self.core.metadata_cache.expire()

    def end_statistics(self, metadata):
        self.end_client_run(self, metadata)
