# This is the bcfg2 support for redhat
# $Id: $

from Toolset import Toolset

def Detect():
    # until the code works
    return False

class Redhat(Toolset):
    '''This class implelements support for rpm packages and standard chkconfig services'''

    def VerifyService(self, entry):
        return False

    def VerifyPackage(self, entry):
        return False

    def InstallService(self, entry):
        return False

    def InstallPackage(self, entry):
        return False


