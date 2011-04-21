import lxml.etree
import Bcfg2.Server.Lint

class Bundles(Bcfg2.Server.Lint.ServerPlugin):
    """ Perform various bundle checks """

    @Bcfg2.Server.Lint.returnErrors
    def Run(self):
        """ run plugin """
        self.missing_bundles()
        self.bundle_names()
        self.sgenshi_groups()

    def missing_bundles(self):
        """ find bundles listed in Metadata but not implemented in Bundler """
        groupdata = self.metadata.groups_xml.xdata
        ref_bundles = set([b.get("name")
                           for b in groupdata.findall("//Bundle")])

        allbundles = self.core.plugins['Bundler'].entries.keys()
        for bundle in ref_bundles:
            xmlbundle = "%s.xml" % bundle
            genshibundle = "%s.genshi" % bundle
            if xmlbundle not in allbundles and genshibundle not in allbundles:
                self.LintError("Bundle %s referenced, but does not exist" %
                               bundle)

    def bundle_names(self):
        """ verify bundle name attribute matches filename """
        for bundle in self.core.plugins['Bundler'].entries.values():
            if self.HandlesFile(bundle.name):
                try:
                    xdata = lxml.etree.XML(bundle.data)
                except AttributeError:
                    # genshi template
                    xdata = lxml.etree.parse(bundle.template.filepath).getroot()
            
                fname = bundle.name.split('Bundler/')[1].split('.')[0]
                bname = xdata.get('name')
                if fname != bname:
                    self.LintWarning("Inconsistent bundle name: filename is %s, bundle name is %s" %
                                     (fname, bname))

    def sgenshi_groups(self):
        """ ensure that Genshi Bundles do not include <Group> tags,
        which are not supported  """
        for bundle in self.core.plugins['Bundler'].entries.values():
            if self.HandlesFile(bundle.name):
                if (type(bundle) is
                    Bcfg2.Server.Plugins.SGenshi.SGenshiTemplateFile):
                    xdata = lxml.etree.parse(bundle.name)
                    groups = [self.RenderXML(g)
                              for g in xdata.getroottree().findall("//Group")]
                    if groups:
                        self.LintWarning("<Group> tag is not allowed in SGenshi Bundle:\n%s" %
                                       "\n".join(groups))
