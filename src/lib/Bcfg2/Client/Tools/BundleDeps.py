""" Bundle dependency support """

import Bcfg2.Client.Tools


class BundleDeps(Bcfg2.Client.Tools.Tool):
    """Bundle dependency helper for Bcfg2. It handles Bundle tags inside the
    bundles that references the required other bundles that should change the
    modification status if the referenced bundles is modified."""

    name = 'Bundle'
    __handles__ = [('Bundle', None)]
    __req__ = {'Bundle': ['name']}

    def InstallBundle(self, _):
        """Simple no-op because we only need the BundleUpdated hook."""
        return dict()

    def VerifyBundle(self, *_):
        """Simple no-op because we only need the BundleUpdated hook."""
        return True

    def BundleUpdated(self, entry):
        """This handles the dependencies on this bundle. It searches all
        Bundle tags in other bundles that references the current bundle name
        and marks those tags as modified to trigger the modification hook on
        the other bundles."""

        bundle_name = entry.get('name')
        for bundle in self.config.findall('./Bundle/Bundle'):
            if bundle.get('name') == bundle_name and \
               bundle not in self.modified:
                self.modified.append(bundle)
        return dict()
