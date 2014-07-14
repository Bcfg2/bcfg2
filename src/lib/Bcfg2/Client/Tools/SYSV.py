"""This provides bcfg2 support for Solaris SYSV packages."""

import tempfile
from Bcfg2.Compat import any  # pylint: disable=W0622
import Bcfg2.Client.Tools
import Bcfg2.Client.XML
import urllib
import copy


# pylint: disable=C0103
noask = '''
mail=
instance=overwrite
partial=nocheck
runlevel=nocheck
idepend=nocheck
rdepend=nocheck
space=ask
setuid=nocheck
conflict=nocheck
action=nocheck
basedir=default
'''
# pylint: enable=C0103


class SYSV(Bcfg2.Client.Tools.PkgTool):
    """Solaris SYSV package support."""
    __execs__ = ["/usr/sbin/pkgadd", "/usr/bin/pkginfo"]
    __handles__ = [('Package', 'sysv')]
    __req__ = {'Package': ['name', 'version']}
    __ireq__ = {'Package': ['name', 'url', 'version']}
    name = 'SYSV'
    pkgtype = 'sysv'
    pkgtool = ("/usr/sbin/pkgadd %s -n -d %%s", (('%s %s', ['url', 'name'])))

    def __init__(self, logger, setup, config):
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, setup, config)
        # noaskfile needs to live beyond __init__ otherwise file is removed
        self.noaskfile = tempfile.NamedTemporaryFile()
        self.noaskname = self.noaskfile.name
        # for any pkg files downloaded
        self.tmpfiles = []
        try:
            self.noaskfile.write(noask)
            # flush admin file contents to disk
            self.noaskfile.flush()
            self.pkgtool = (self.pkgtool[0] % ("-a %s" % (self.noaskname)),
                            self.pkgtool[1])
        except:  # pylint: disable=W0702
            self.pkgtool = (self.pkgtool[0] % "", self.pkgtool[1])

    def pkgmogrify(self, pkg):
        """ Take a pkg object, check for a 'simplename' attribute. If found,
            return a modified pkg object that points to to a temporary file
        """
        if pkg.get('simplename'):
            self.logger.debug("Pkgmogrifying %s because simplename %s found" %
                              (pkg.get('name'), pkg.get('simplename')))
            tmpfile = tempfile.NamedTemporaryFile()
            self.tmpfiles.append(tmpfile)
            self.logger.debug("URL: %s/%s" %
                              (pkg.get('url'), pkg.get('simplename')))
            urllib.urlretrieve("%s/%s" %
                               (pkg.get('url'), pkg.get('simplename')),
                               tmpfile.name)
            newpkg = copy.copy(pkg)
            newpkg.set('url', tmpfile.name)
            return newpkg
        return pkg

    def Install(self, packages, states):
        for pkg in packages:
            pkg = self.pkgmogrify(pkg)
            if self.VerifyPackage(pkg, []):
                self.logger.info("Forcing state to true for pkg %s" %
                                 (pkg.get('name')))
                states[pkg] = True
            else:
                self.logger.info("Installing pkg %s version %s" %
                                 (pkg.get('name'), pkg.get('version')))

                if self.cmd.run(self._get_package_command([pkg])):
                    states[pkg] = True
                else:
                    self.logger.error("Failed to install package %s" %
                                      pkg.get('name'))

            self.RefreshPackages()
        self.modified.extend(entry for entry in packages if states[entry])

    def RefreshPackages(self):
        """Refresh memory hashes of packages."""
        self.installed = {}
        # Build list of packages
        lines = self.cmd.run("/usr/bin/pkginfo -x").stdout.splitlines()
        while lines:
            # Splitting on whitespace means that packages with spaces in
            # their version numbers don't work right.  Found this with
            # IBM TSM software with package versions like
            #           "Version 6 Release 1 Level 0.0"
            # Should probably be done with a regex but this works.
            version = lines.pop().split(') ')[1]
            pkg = lines.pop().split()[0]
            self.installed[pkg] = version

    def VerifyPackage(self, entry, modlist):
        """Verify Package status for entry."""
        desired_version = entry.get('version')
        if desired_version == 'any':
            desired_version = self.installed.get(entry.get('name'),
                                                 desired_version)

        if not self.cmd.run(["/usr/bin/pkginfo", "-q", "-v",
                             desired_version, entry.get('name')]):
            if entry.get('name') in self.installed:
                self.logger.debug("Package %s version incorrect: "
                                  "have %s want %s" %
                                  (entry.get('name'),
                                   self.installed[entry.get('name')],
                                   desired_version))
            else:
                self.logger.debug("Package %s not installed" %
                                  entry.get("name"))
        else:
            if self.setup['quick'] or \
               entry.attrib.get('verify', 'true') == 'false':
                return True
            rv = self.cmd.run("/usr/sbin/pkgchk -n %s" % entry.get('name'))
            if rv.success:
                return True
            else:
                output = [line for line in rv.stdout.splitlines()
                          if line[:5] == 'ERROR']
                if any(name for name in output
                       if name.split()[-1] not in modlist):
                    self.logger.debug("Package %s content verification failed"
                                      % entry.get('name'))
                else:
                    return True
        return False

    def Remove(self, packages):
        """Remove specified Sysv packages."""
        names = [pkg.get('name') for pkg in packages]
        self.logger.info("Removing packages: %s" % (names))
        self.cmd.run("/usr/sbin/pkgrm -a %s -n %s" %
                     (self.noaskname, names))
        self.RefreshPackages()
        self.extra = self.FindExtra()
