"""This provides bundle clauses with translation functionality."""

import os
import re
import sys
import Bcfg2.Server
import Bcfg2.Server.Plugin
import Bcfg2.Server.Lint
from genshi.template import TemplateError


class BundleFile(Bcfg2.Server.Plugin.StructFile):
    """ Representation of a bundle XML file """
    bundle_name_re = re.compile('^(?P<name>.*)\.(xml|genshi)$')

    def __init__(self, filename, should_monitor=False):
        Bcfg2.Server.Plugin.StructFile.__init__(self, filename,
                                                should_monitor=should_monitor)
        if self.name.endswith(".genshi"):
            self.logger.warning("Bundler: Bundle filenames ending with "
                                ".genshi are deprecated; add the Genshi XML "
                                "namespace to a .xml bundle instead")
    __init__.__doc__ = Bcfg2.Server.Plugin.StructFile.__init__.__doc__

    def Index(self):
        Bcfg2.Server.Plugin.StructFile.Index(self)
        if self.xdata.get("name"):
            self.logger.warning("Bundler: Explicitly specifying bundle names "
                                "is deprecated")
    Index.__doc__ = Bcfg2.Server.Plugin.StructFile.Index.__doc__

    @property
    def bundle_name(self):
        """ The name of the bundle, as determined from the filename """
        return self.bundle_name_re.match(
            os.path.basename(self.name)).group("name")


class Bundler(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.Structure,
              Bcfg2.Server.Plugin.XMLDirectoryBacked):
    """ The bundler creates dependent clauses based on the
    bundle/translation scheme from Bcfg1. """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __child__ = BundleFile

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Structure.__init__(self)
        Bcfg2.Server.Plugin.XMLDirectoryBacked.__init__(self, self.data)
        #: Bundles by bundle name, rather than filename
        self.bundles = dict()
    __init__.__doc__ = Bcfg2.Server.Plugin.Plugin.__init__.__doc__

    def HandleEvent(self, event):
        Bcfg2.Server.Plugin.XMLDirectoryBacked.HandleEvent(self, event)

        self.bundles = dict()
        for bundle in self.entries.values():
            self.bundles[bundle.bundle_name] = bundle
    HandleEvent.__doc__ = \
        Bcfg2.Server.Plugin.XMLDirectoryBacked.HandleEvent.__doc__

    def BuildStructures(self, metadata):
        bundleset = []
        for bundlename in metadata.bundles:
            try:
                bundle = self.bundles[bundlename]
            except KeyError:
                self.logger.error("Bundler: Bundle %s does not exist" %
                                  bundlename)
                continue
            try:
                bundleset.append(bundle.XMLMatch(metadata))
            except TemplateError:
                err = sys.exc_info()[1]
                self.logger.error("Bundler: Failed to render templated bundle "
                                  "%s: %s" % (bundlename, err))
            except:
                self.logger.error("Bundler: Unexpected bundler error for %s" %
                                  bundlename, exc_info=1)
        return bundleset
    BuildStructures.__doc__ = \
        Bcfg2.Server.Plugin.Structure.BuildStructures.__doc__


class BundlerLint(Bcfg2.Server.Lint.ServerPlugin):
    """ Perform various bundle checks """

    def Run(self):
        """ run plugin """
        self.missing_bundles()
        for bundle in self.core.plugins['Bundler'].entries.values():
            if self.HandlesFile(bundle.name):
                self.bundle_names(bundle)

    @classmethod
    def Errors(cls):
        return {"bundle-not-found": "error",
                "unused-bundle": "warning",
                "explicit-bundle-name": "error",
                "genshi-extension-bundle": "error"}

    def missing_bundles(self):
        """ find bundles listed in Metadata but not implemented in Bundler """
        if self.files is None:
            # when given a list of files on stdin, this check is
            # useless, so skip it
            groupdata = self.metadata.groups_xml.xdata
            ref_bundles = set([b.get("name")
                               for b in groupdata.findall("//Bundle")])

            allbundles = self.core.plugins['Bundler'].bundles.keys()
            for bundle in ref_bundles:
                if bundle not in allbundles:
                    self.LintError("bundle-not-found",
                                   "Bundle %s referenced, but does not exist" %
                                   bundle)

            for bundle in allbundles:
                if bundle not in ref_bundles:
                    self.LintError("unused-bundle",
                                   "Bundle %s defined, but is not referenced "
                                   "in Metadata" % bundle)

    def bundle_names(self, bundle):
        """ Verify that deprecated bundle .genshi bundles and explicit
        bundle names aren't used """
        if bundle.xdata.get('name'):
            self.LintError("explicit-bundle-name",
                           "Deprecated explicit bundle name in %s" %
                           bundle.name)

        if bundle.name.endswith(".genshi"):
            self.LintError("genshi-extension-bundle",
                           "Bundle %s uses deprecated .genshi extension" %
                           bundle.name)
