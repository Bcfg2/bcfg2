"""This provides bundle clauses with translation functionality."""

import os
import re
import sys
import copy
import lxml.etree
import Bcfg2.Server
import Bcfg2.Server.Plugin
import Bcfg2.Server.Lint
from genshi.template import TemplateError


class BundleFile(Bcfg2.Server.Plugin.StructFile):
    """ Representation of a bundle XML file """
    def get_xml_value(self, metadata):
        """ get the XML data that applies to the given client """
        bundle = lxml.etree.Element('Bundle', name=self.xdata.get("name"))
        for item in self.Match(metadata):
            bundle.append(copy.copy(item))
        return bundle


class Bundler(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.Structure,
              Bcfg2.Server.Plugin.XMLDirectoryBacked):
    """ The bundler creates dependent clauses based on the
    bundle/translation scheme from Bcfg1. """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    __child__ = BundleFile
    patterns = re.compile('^(?P<name>.*)\.(xml|genshi)$')

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Structure.__init__(self)
        try:
            Bcfg2.Server.Plugin.XMLDirectoryBacked.__init__(self, self.data)
        except OSError:
            err = sys.exc_info()[1]
            msg = "Failed to load Bundle repository %s: %s" % (self.data, err)
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginInitError(msg)

    def BuildStructures(self, metadata):
        """Build all structures for client (metadata)."""
        bundleset = []

        bundle_entries = {}
        for key, item in self.entries.items():
            bundle_entries.setdefault(
                self.patterns.match(os.path.basename(key)).group('name'),
                []).append(item)

        for bundlename in metadata.bundles:
            try:
                entries = bundle_entries[bundlename]
            except KeyError:
                self.logger.error("Bundler: Bundle %s does not exist" %
                                  bundlename)
                continue
            try:
                bundleset.append(entries[0].get_xml_value(metadata))
            except TemplateError:
                err = sys.exc_info()[1]
                self.logger.error("Bundler: Failed to render templated bundle "
                                  "%s: %s" % (bundlename, err))
            except:
                self.logger.error("Bundler: Unexpected bundler error for %s" %
                                  bundlename, exc_info=1)
        return bundleset


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
                "inconsistent-bundle-name": "warning"}

    def missing_bundles(self):
        """ find bundles listed in Metadata but not implemented in Bundler """
        if self.files is None:
            # when given a list of files on stdin, this check is
            # useless, so skip it
            groupdata = self.metadata.groups_xml.xdata
            ref_bundles = set([b.get("name")
                               for b in groupdata.findall("//Bundle")])

            allbundles = self.core.plugins['Bundler'].entries.keys()
            for bundle in ref_bundles:
                xmlbundle = "%s.xml" % bundle
                genshibundle = "%s.genshi" % bundle
                if (xmlbundle not in allbundles and
                    genshibundle not in allbundles):
                    self.LintError("bundle-not-found",
                                   "Bundle %s referenced, but does not exist" %
                                   bundle)

    def bundle_names(self, bundle):
        """ verify bundle name attribute matches filename """
        fname = os.path.splitext(os.path.basename(bundle.name))[0]
        bname = bundle.xdata.get('name')
        if fname != bname:
            self.LintError("inconsistent-bundle-name",
                           "Inconsistent bundle name: filename is %s, "
                           "bundle name is %s" % (fname, bname))
