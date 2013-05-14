"""This provides bundle clauses with translation functionality."""

import copy
import logging
import lxml.etree
import os
import os.path
import re
import sys
import Bcfg2.Server
import Bcfg2.Server.Plugin
import Bcfg2.Server.Lint

try:
    import genshi.template.base
    from Bcfg2.Server.Plugins.TGenshi import removecomment, TemplateFile
    HAS_GENSHI = True
except ImportError:
    HAS_GENSHI = False


SETUP = None


class BundleFile(Bcfg2.Server.Plugin.StructFile):
    """ Representation of a bundle XML file """
    def get_xml_value(self, metadata):
        """ get the XML data that applies to the given client """
        bundlename = os.path.splitext(os.path.basename(self.name))[0]
        bundle = lxml.etree.Element('Bundle', name=bundlename)
        for item in self.Match(metadata):
            bundle.append(copy.copy(item))
        return bundle


if HAS_GENSHI:
    class BundleTemplateFile(TemplateFile,
                             Bcfg2.Server.Plugin.StructFile):
        """ Representation of a Genshi-templated bundle XML file """

        def __init__(self, name, specific, encoding):
            TemplateFile.__init__(self, name, specific, encoding)
            Bcfg2.Server.Plugin.StructFile.__init__(self, name)
            self.logger = logging.getLogger(name)

        def get_xml_value(self, metadata):
            """ get the rendered XML data that applies to the given
            client """
            if not hasattr(self, 'template'):
                msg = "No parsed template information for %s" % self.name
                self.logger.error(msg)
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
            stream = self.template.generate(
                metadata=metadata,
                repo=SETUP['repo']).filter(removecomment)
            data = lxml.etree.XML(stream.render('xml',
                                                strip_whitespace=False),
                                  parser=Bcfg2.Server.XMLParser)
            bundlename = os.path.splitext(os.path.basename(self.name))[0]
            bundle = lxml.etree.Element('Bundle', name=bundlename)
            for item in self.Match(metadata, data):
                bundle.append(copy.deepcopy(item))
            return bundle

        def Match(self, metadata, xdata):  # pylint: disable=W0221
            """Return matching fragments of parsed template."""
            rv = []
            for child in xdata.getchildren():
                rv.extend(self._match(child, metadata))
            self.logger.debug("File %s got %d match(es)" % (self.name,
                                                            len(rv)))
            return rv

    class SGenshiTemplateFile(BundleTemplateFile):
        """ provided for backwards compat with the deprecated SGenshi
        plugin """
        pass


class Bundler(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.Structure,
              Bcfg2.Server.Plugin.XMLDirectoryBacked):
    """ The bundler creates dependent clauses based on the
    bundle/translation scheme from Bcfg1. """
    __author__ = 'bcfg-dev@mcs.anl.gov'
    patterns = re.compile(r'^(?P<name>.*)\.(xml|genshi)$')

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Structure.__init__(self)
        self.encoding = core.setup['encoding']
        self.__child__ = self.template_dispatch
        Bcfg2.Server.Plugin.XMLDirectoryBacked.__init__(self, self.data,
                                                        self.core.fam)
        global SETUP
        SETUP = core.setup

    def template_dispatch(self, name, _):
        """ Add the correct child entry type to Bundler depending on
        whether the XML file in question is a plain XML file or a
        templated bundle """
        bundle = lxml.etree.parse(name, parser=Bcfg2.Server.XMLParser)
        nsmap = bundle.getroot().nsmap
        if (name.endswith('.genshi') or
            ('py' in nsmap and
             nsmap['py'] == 'http://genshi.edgewall.org/')):
            if HAS_GENSHI:
                spec = Bcfg2.Server.Plugin.Specificity()
                return BundleTemplateFile(name, spec, self.encoding)
            else:
                raise Bcfg2.Server.Plugin.PluginExecutionError("Genshi not "
                                                               "available: %s"
                                                               % name)
        else:
            return BundleFile(name, self.fam)

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
            except genshi.template.base.TemplateError:
                err = sys.exc_info()[1]
                self.logger.error("Bundler: Failed to render templated bundle "
                                  "%s: %s" % (bundlename, err))
            except:
                self.logger.error("Bundler: Unexpected bundler error for %s" %
                                  bundlename, exc_info=1)
        return bundleset


class BundlerLint(Bcfg2.Server.Lint.ServerPlugin):
    """ Perform various :ref:`Bundler
    <server-plugins-structures-bundler-index>` checks. """

    def Run(self):
        self.missing_bundles()
        for bundle in self.core.plugins['Bundler'].entries.values():
            if (self.HandlesFile(bundle.name) and
                (not HAS_GENSHI or
                 not isinstance(bundle, BundleTemplateFile))):
                self.bundle_names(bundle)

    @classmethod
    def Errors(cls):
        return {"bundle-not-found": "error",
                "inconsistent-bundle-name": "warning"}

    def missing_bundles(self):
        """ Find bundles listed in Metadata but not implemented in
        Bundler. """
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
        """ Verify bundle name attribute matches filename.

        :param bundle: The bundle to verify
        :type bundle: Bcfg2.Server.Plugins.Bundler.BundleFile
        """
        try:
            xdata = lxml.etree.XML(bundle.data)
        except AttributeError:
            # genshi template
            xdata = lxml.etree.parse(bundle.template.filepath).getroot()

        fname = os.path.splitext(os.path.basename(bundle.name))[0]
        bname = xdata.get('name')
        if fname != bname:
            self.LintError("inconsistent-bundle-name",
                           "Inconsistent bundle name: filename is %s, "
                           "bundle name is %s" % (fname, bname))
