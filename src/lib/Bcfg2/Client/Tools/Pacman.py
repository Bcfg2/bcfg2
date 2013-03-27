"""This is the bcfg2 support for pacman"""

import sys
import Bcfg2.Client.Tools


class Pacman(Bcfg2.Client.Tools.PkgTool):
    '''Archlinux package support'''
    name = 'Pacman'
    __execs__ = ["/usr/bin/pacman"]
    __handles__ = [('Package', 'pacman')]
    __req__ = {'Package': ['name', 'version']}
    pkgtype = 'pacman'
    pkgtool = ("/usr/bin/pacman --needed --noconfirm --noprogressbar")

    def __init__(self, logger, setup, config):
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, setup, config)
        self.installed = {}
        self.RefreshPackages()

    def RefreshPackages(self):
        '''Refresh memory hashes of packages'''
        self.installed = {}
        for pkg in self.cmd.run("/usr/bin/pacman -Q").stdout.splitlines():
            pkgname = pkg.split(' ')[0].strip()
            version = pkg.split(' ')[1].strip()
            #self.logger.info(" pkgname: %s, version: %s" % (pkgname, version))
            self.installed[pkgname] = version

    def VerifyPackage(self, entry, _):
        '''Verify Package status for entry'''

        self.logger.info("VerifyPackage: %s : %s" % (entry.get('name'),
                                                     entry.get('version')))

        if not 'version' in entry.attrib:
            self.logger.info("Cannot verify unversioned package %s" %
                             entry.attrib['name'])
            return False

        if entry.attrib['name'] in self.installed:
            if entry.attrib['version'] == 'auto':
                return True
            elif self.installed[entry.attrib['name']] == \
                    entry.attrib['version']:
                #if not self.setup['quick'] and \
                #                entry.get('verify', 'true') == 'true':
                #FIXME: need to figure out if pacman
                #       allows you to verify packages
                return True
            else:
                entry.set('current_version', self.installed[entry.get('name')])
                self.logger.info("attribname: %s" % (entry.attrib['name']))
                self.logger.info("attribname: %s" % (entry.attrib['name']))
                return False
        entry.set('current_exists', 'false')
        self.logger.info("attribname: %s" % (entry.attrib['name']))
        return False

    def Remove(self, packages):
        '''Remove extra packages'''
        names = [pkg.get('name') for pkg in packages]
        self.logger.info("Removing packages: %s" % " ".join(names))
        self.cmd.run("%s --noconfirm --noprogressbar -R %s" %
                     (self.pkgtool, " ".join(names)))
        self.RefreshPackages()
        self.extra = self.FindExtra()

    def Install(self, packages, states):
        '''
        Pacman Install
        '''
        pkgline = ""
        for pkg in packages:
            pkgline += " " + pkg.get('name')

        self.logger.info("packages : " + pkgline)

        try:
            self.logger.debug("Running : %s -S %s" % (self.pkgtool, pkgline))
            self.cmd.run("%s -S %s" % (self.pkgtool, pkgline))
        except:  # pylint: disable=W0702
            err = sys.exc_info()[1]
            self.logger.error("Error occurred during installation: %s" % err)
