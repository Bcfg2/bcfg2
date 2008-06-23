'''Fingerprint mode for bcfg2-admin'''

import Bcfg2.tlslite.api
import Bcfg2.Server.Admin

class Fingerprint(Bcfg2.Server.Admin.Mode):
    '''Produce server key fingerprint'''
    __shorthelp__ = 'bcfg2-admin fingerprint'
    __longhelp__ = __shorthelp__ + '\n\tPrint the server certificate fingerprint'
    
    def __init__(self, cfile):
	Bcfg2.Server.Admin.Mode.__init__(self, cfile)	

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        print self.getFingerprint()

    def getFingerprint(self):
        '''calculate key fingerprint'''
        keypath = self.cfp.get('communication', 'key')
        x509 = Bcfg2.tlslite.api.X509()
        x509.parse(open(keypath).read())
        return x509.getFingerprint()
