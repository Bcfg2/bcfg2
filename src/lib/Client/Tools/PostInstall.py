'''PostInstall Support'''
__revision__ = '$Revision$'

import Bcfg2.Client.Tools

class PostInstall(Bcfg2.Client.Tools.Tool):
    '''Implement PostInstalls'''
    __name__ = 'PostInstall'
    __handles__ = [('PostInstall', None)]
    __req__ = {'PostInstall': ['name']}
    
    def VerifyPostInstall(self, dummy, _):
        '''PostInstalls always verify true'''
        return True

    def BundleUpdated(self, bundle, states):
        '''Run postinstalls when bundles have been updated'''
        for entry in bundle:
            if entry.tag == 'PostInstall':
                self.cmd.run(entry.get('name'))
        
