import lxml.etree
import Bcfg2.Server.Lint

class Bundles(Bcfg2.Server.Lint.ServerPlugin):
    """ Perform various bundle checks """
    def Run(self):
        """ run plugin """
        if 'Bundler' in self.core.plugins:
            self.missing_bundles()
            for bundle in self.core.plugins['Bundler'].entries.values():
                if self.HandlesFile(bundle.name):
                    if (not Bcfg2.Server.Plugins.Bundler.have_genshi or
                        type(bundle) is not
                        Bcfg2.Server.Plugins.SGenshi.SGenshiTemplateFile):
                        self.bundle_names(bundle)

    def Errors(self):
        return {"bundle-not-found":"error",
                "inconsistent-bundle-name":"warning"}

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
        try:
            xdata = lxml.etree.XML(bundle.data)
        except AttributeError:
            # genshi template
            xdata = lxml.etree.parse(bundle.template.filepath).getroot()

        fname = bundle.name.split('Bundler/')[1].split('.')[0]
        bname = xdata.get('name')
        if fname != bname:
            self.LintError("inconsistent-bundle-name",
                           "Inconsistent bundle name: filename is %s, bundle name is %s" %
                           (fname, bname))
