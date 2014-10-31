""" ``bcfg2-lint`` plugin for :ref:`Bundler
<server-plugins-structures-bundler>` """

from Bcfg2.Server.Lint import ServerPlugin


class Bundler(ServerPlugin):
    """ Perform various :ref:`Bundler
    <server-plugins-structures-bundler>` checks. """
    __serverplugin__ = 'Bundler'

    def Run(self):
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
        """ Find bundles listed in Metadata but not implemented in
        Bundler. """
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
