"""This provides bundle clauses with translation functionality."""

import os
import re
import sys
import copy
import Bcfg2.Server
import Bcfg2.Server.Plugin
from genshi.template import TemplateError


class BundleFile(Bcfg2.Server.Plugin.StructFile):
    """ Representation of a bundle XML file """
    bundle_name_re = re.compile(r'^(?P<name>.*)\.(xml|genshi)$')

    def __init__(self, filename, should_monitor=False):
        Bcfg2.Server.Plugin.StructFile.__init__(self, filename,
                                                should_monitor=should_monitor)
        if self.name.endswith(".genshi"):
            self.logger.warning("Bundler: %s: Bundle filenames ending with "
                                ".genshi are deprecated; add the Genshi XML "
                                "namespace to a .xml bundle instead" %
                                self.name)
    __init__.__doc__ = Bcfg2.Server.Plugin.StructFile.__init__.__doc__

    def Index(self):
        Bcfg2.Server.Plugin.StructFile.Index(self)
        if self.xdata.get("name"):
            self.logger.warning("Bundler: %s: Explicitly specifying bundle "
                                "names is deprecated" % self.name)
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
    patterns = re.compile(r'^.*\.(?:xml|genshi)$')

    def __init__(self, core):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core)
        Bcfg2.Server.Plugin.Structure.__init__(self)
        Bcfg2.Server.Plugin.XMLDirectoryBacked.__init__(self, self.data)
        #: Bundles by bundle name, rather than filename
        self.bundles = dict()

    def HandleEvent(self, event):
        Bcfg2.Server.Plugin.XMLDirectoryBacked.HandleEvent(self, event)

        self.bundles = dict([(b.bundle_name, b)
                             for b in self.entries.values()])

    def BuildStructures(self, metadata):
        bundleset = []
        bundles = copy.copy(metadata.bundles)
        bundles_added = set(bundles)
        while bundles:
            bundlename = bundles.pop()
            try:
                bundle = self.bundles[bundlename]
            except KeyError:
                self.logger.error("Bundler: Bundle %s does not exist" %
                                  bundlename)
                continue

            try:
                data = bundle.XMLMatch(metadata)
            except TemplateError:
                err = sys.exc_info()[1]
                self.logger.error("Bundler: Failed to render templated bundle "
                                  "%s: %s" % (bundlename, err))
                continue
            except:
                self.logger.error("Bundler: Unexpected bundler error for %s" %
                                  bundlename, exc_info=1)
                continue

            if data.get("independent", "false").lower() == "true":
                data.tag = "Independent"
                del data.attrib['independent']

            data.set("name", bundlename)

            for child in data.findall("Bundle"):
                if child.getchildren():
                    # XInclude'd bundle -- "flatten" it so there
                    # aren't extra Bundle tags, since other bits in
                    # Bcfg2 only handle the direct children of the
                    # top-level Bundle tag
                    if data.get("name"):
                        self.logger.warning("Bundler: In file XIncluded from "
                                            "%s: Explicitly specifying "
                                            "bundle names is deprecated" %
                                            self.name)
                    for el in child.getchildren():
                        data.append(el)
                    data.remove(child)
                elif child.get("name"):
                    # dependent bundle -- add it to the list of
                    # bundles for this client
                    if child.get("name") not in bundles_added:
                        bundles.append(child.get("name"))
                        bundles_added.add(child.get("name"))
                    data.remove(child)
                else:
                    # neither name or children -- wat
                    self.logger.warning("Bundler: Useless empty Bundle tag "
                                        "in %s" % self.name)
                    data.remove(child)
            bundleset.append(data)
        return bundleset
