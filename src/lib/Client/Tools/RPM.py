'''Bcfg2 Support for RPMS'''

__revision__ = '$Revision$'

import Bcfg2.Client.Tools, time

class RPM(Bcfg2.Client.Tools.PkgTool):
    '''Support for RPM packages'''
    __name__ = 'RPM'
    __execs__ = ['/bin/rpm']
    __handles__ = [('Package', 'rpm')]
    __req__ = {'Package': ['name', 'version', 'url']}
    pkgtype = 'rpm'
    pkgtool = ("rpm --oldpackage --replacepkgs --quiet -U %s", ("%s", ["url"]))

    def RefreshPackages(self, level=0):
        '''Cache package states'''
        self.installed = {}
        if level > 5:
            return
        for line in self.cmd.run("rpm -qa --qf '%{NAME} %{VERSION}-%{RELEASE}\n'")[1]:
            try:
                (name, version) = line.split()
                self.installed[name] = version
            except ValueError:
                if line == '':
                    continue
                self.logger.error("Failed to access RPM db; retrying after 30s")
                time.sleep(30)
                return self.RefreshPackages(level + 1)

    def VerifyPackage(self, entry, modlist):
        '''Verify Package status for entry'''
        if not entry.get('version'):
            self.logger.error("Can't install package %s, not enough data." % (entry.get('name')))
            return False
        rpm_options = []
        if entry.get('verify', 'false') == 'nomtime':
            self.logger.debug("Skipping mtime verification for package %s" % (entry.get('name')))
            rpm_options.append("--nomtime")
        if self.installed.has_key(entry.get('name')):
            if entry.get('version') == self.installed[entry.get('name')]:
                if entry.get('multiarch'):
                    archs = entry.get('multiarch').split()
                    info = self.cmd.run('rpm -q %s --qf "%%{NAME} %%{VERSION}-%%{RELEASE} %%{ARCH}\n"' % (entry.get('name')))[1]
                    while info:
                        arch = info.pop().split()[2]
                        if arch in archs:
                            archs.remove(arch)
                        else:
                            self.logger.error("Got pkg install for Package %s: arch %s" % (entry.get('name'), arch))
                            return False
                    if archs:
                        self.logger.error("Package %s not installed for arch: %s" % (entry.get('name'), archs))
                        return False
                if (self.setup['quick'] or (entry.get('verify', 'true') == 'false')) or entry.get('multiarch'):
                    if entry.get('verify', 'true') == 'false':
                        self.logger.debug("Skipping checksum verification for package %s" % (entry.get('name')))
                    return True
            else:
                self.logger.debug("Package %s: wrong version installed. want %s have %s" %
                                  (entry.get('name'), entry.get('version'), self.installed[entry.get('name')]))
                entry.set('current_version', self.installed[entry.get('name')])
                return False
        else:
            self.logger.debug("Package %s: not installed" % (entry.get('name')))
            entry.set('current_exists', 'false')
            return False

        (vstat, output) = self.cmd.run("rpm --verify -q %s %s-%s" % (" ".join(rpm_options), entry.get('name'), entry.get('version')))
        if vstat != 0:
            if [name for name in output if name.split()[-1] not in modlist]:
                self.logger.debug("Package %s content verification failed" % entry.get('name'))
                return False
        return True

    def RemovePackages(self, entries):
        '''Remove specified entries'''
        pkgnames = " ".join([entry[2] for entry in entries])
        if len(pkgnames) > 0:
            self.logger.info("Removing packages: %s" % pkgnames)
            self.cmd.run("rpm --quiet -e --allmatches %s" % " ".join(pkgnames))
            self.RefreshPackages()
            self.extra = self.FindExtraPackages()
