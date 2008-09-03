'''This is the bcfg2 support for apt-get'''
__revision__ = '$Revision$'

import apt_pkg
import os, re
import Bcfg2.Client.Tools

class APT(Bcfg2.Client.Tools.PkgTool):
    '''The Debian toolset implements package and service operations and inherits
    the rest from Toolset.Toolset'''
    __name__ = 'APT'
    __execs__ = ['/usr/bin/debsums', '/usr/bin/apt-get', '/usr/bin/dpkg']
    __important__ = ["/etc/apt/sources.list",
                     "/var/cache/debconf/config.dat", 
                     "/var/cache/debconf/templates.dat",
                     '/etc/passwd', '/etc/group', 
                     '/etc/apt/apt.conf', '/etc/dpkg/dpkg.cfg']
    __handles__ = [('Package', 'deb')]
    __req__ = {'Package': ['name', 'version']}
    pkgtype = 'deb'
    pkgtool = ('apt-get -o DPkg::Options::=--force-overwrite -o DPkg::Options::=--force-confold --reinstall -q=2 --force-yes -y install %s',
               ('%s=%s', ['name', 'version']))
    
    svcre = re.compile("/etc/.*/[SK]\d\d(?P<name>\S+)")

    def __init__(self, logger, cfg, setup):
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, cfg, setup)
        self.cfg = cfg
        os.environ["DEBIAN_FRONTEND"] = 'noninteractive'
        self.updated = False

    def RefreshPackages(self):
        '''Refresh memory hashes of packages'''
        apt_pkg.init()
        cache = apt_pkg.GetCache()
        self.installed = {}
        for pkg in cache.Packages:
            if pkg.CurrentVer:
                self.installed[pkg.Name] = pkg.CurrentVer.VerStr
        self.extra = self.FindExtraPackages()

    def VerifyPackage(self, entry, modlist):
        '''Verify package for entry'''
        if not entry.attrib.has_key('version'):
            self.logger.info("Cannot verify unversioned package %s" %
                             (entry.attrib['name']))
            return False
        if self.installed.has_key(entry.attrib['name']):
            if self.installed[entry.attrib['name']] == entry.attrib['version']:
                if not self.setup['quick'] and entry.get('verify', 'true') == 'true':
                    output = self.cmd.run("/usr/bin/debsums -as %s" % entry.get('name'))[1]
                    if len(output) == 1 and "no md5sums for" in output[0]:
                        self.logger.info("Package %s has no md5sums. Cannot verify" % \
                                         entry.get('name'))
                        entry.set('qtext', "Reinstall Package %s-%s to setup md5sums? (y/N) " \
                                  % (entry.get('name'), entry.get('version')))
                        return False
                    files = []
                    for item in output:
                        if "checksum mismatch" in item:
                            files.append(item.split()[-1])
                        elif "can't open" in item:
                            files.append(item.split()[5])
                        elif "is not installed" in item:
                            self.logger.error("Package %s is not fully installed" \
                                              % entry.get('name'))
                        else:
                            self.logger.error("Got Unsupported pattern %s from debsums" \
                                              % item)
                            files.append(item)
                    # We check if there is file in the checksum to do
                    if files:
                        # if files are found there we try to be sure our modlist is sane
                        # with erroneous symlinks
                        modlist = [os.path.realpath(filename) for filename in modlist]
                    bad = [filename for filename in files if filename not in modlist]
                    if bad:
                        self.logger.info("Package %s failed validation. Bad files are:" % \
                                         entry.get('name'))
                        self.logger.info(bad)
                        entry.set('qtext',
                                  "Reinstall Package %s-%s to fix failing md5sums? (y/N) " % (entry.get('name'), entry.get('version')))
                        return False
                return True
            else:
                entry.set('current_version', self.installed[entry.get('name')])
                entry.set('qtext', "Upgrade/downgrade Package %s (%s -> %s)? (y/N) " % \
                          (entry.get('name'), entry.get('current_version'),
                           entry.get('version')))
                return False
        self.logger.info("Package %s not installed" % (entry.get('name')))
        entry.set('current_exists', 'false')
        return False

    def RemovePackages(self, packages):
        '''Deal with extra configuration detected'''
        pkgnames = " ".join([pkg.get('name') for pkg in packages])
        if len(packages) > 0:
            self.logger.info('Removing packages:')
            self.logger.info(pkgnames)
            if self.cmd.run("apt-get remove -y --force-yes %s" % pkgnames)[0] == 0:
                self.modified += packages
            self.RefreshPackages()
            self.extra = self.FindExtraPackages()
              
    def Install(self, packages, states):
        if self.setup['kevlar'] and not self.setup['dryrun'] and not self.updated:
            self.cmd.run("dpkg --force-confold --configure --pending")
            self.cmd.run("apt-get clean")
            self.cmd.run("apt-get -q=2 -y update")
            self.updated = True
        Bcfg2.Client.Tools.PkgTool.Install(self, packages, states)
