# This is the bcfg2 support for gentoo
# $Id: $

from Toolset import Toolset

def Detect():
    # until the code works
    return False

class Gentoo(Toolset):
    '''This class implelements support for emerge packages and standard rc-update services'''

    def VerifyService(self, entry):
        return False

    def VerifyPackage(self, entry):
        return False

    def InstallService(self, entry):
        return False

    def InstallPackage(self, entry):
        return False


