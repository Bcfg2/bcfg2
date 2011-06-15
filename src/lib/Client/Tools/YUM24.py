"""This provides bcfg2 support for yum."""
__revision__ = '$Revision: $'

import copy
import os.path
import sys
import yum
import Bcfg2.Client.XML
import Bcfg2.Client.Tools.RPMng
# Compatibility import
from Bcfg2.Bcfg2Py3k import ConfigParser

# Fix for python2.3
try:
    set
except NameError:
    from sets import Set as set

YAD = True
CP = ConfigParser.ConfigParser()
try:
    if '-C' in sys.argv:
        CP.read([sys.argv[sys.argv.index('-C') + 1]])
    else:
        CP.read(['/etc/bcfg2.conf'])
    if CP.get('YUMng', 'autodep').lower() == 'false':
        YAD = False
except:
    pass

if not hasattr(Bcfg2.Client.Tools.RPMng, 'RPMng'):
    raise ImportError


def build_yname(pkgname, inst):
    """Build yum appropriate package name."""
    ypname = pkgname
    if inst.get('version') != 'any':
        ypname += '-'
    if inst.get('epoch', False):
        ypname += "%s:" % inst.get('epoch')
    if inst.get('version', False) and inst.get('version') != 'any':
        ypname += "%s" % (inst.get('version'))
    if inst.get('release', False) and inst.get('release') != 'any':
        ypname += "-%s" % (inst.get('release'))
    if inst.get('arch', False) and inst.get('arch') != 'any':
        ypname += ".%s" % (inst.get('arch'))
    return ypname


class YUM24(Bcfg2.Client.Tools.RPMng.RPMng):
    """Support for Yum packages."""
    pkgtype = 'yum'

    name = 'YUM24'
    __execs__ = ['/usr/bin/yum', '/var/lib/rpm']
    __handles__ = [('Package', 'yum'),
                   ('Package', 'rpm'),
                   ('Path', 'ignore')]

    __req__ = {'Package': ['name', 'version']}
    __ireq__ = {'Package': ['name']}
    #__ireq__ = {'Package': ['name', 'version']}

    __new_req__ = {'Package': ['name'],
                   'Instance': ['version', 'release', 'arch']}
    __new_ireq__ = {'Package': ['name'], \
                    'Instance': []}
    #__new_ireq__ = {'Package': ['name', 'uri'], \
    #                'Instance': ['simplefile', 'version', 'release', 'arch']}

    __gpg_req__ = {'Package': ['name', 'version']}
    __gpg_ireq__ = {'Package': ['name', 'version']}

    __new_gpg_req__ = {'Package': ['name'],
                       'Instance': ['version', 'release']}
    __new_gpg_ireq__ = {'Package': ['name'],
                        'Instance': ['version', 'release']}

    def __init__(self, logger, setup, config):
        Bcfg2.Client.Tools.RPMng.RPMng.__init__(self, logger, setup, config)
        self.__important__ = self.__important__ + \
                             [entry.get('name') for struct in config \
                              for entry in struct \
                              if entry.tag in ['Path', 'ConfigFile'] and \
                              (entry.get('name').startswith('/etc/yum.d') \
                              or entry.get('name').startswith('/etc/yum.repos.d')) \
                              or entry.get('name') == '/etc/yum.conf']
        self.yum_avail = dict()
        self.yum_installed = dict()
        self.yb = yum.YumBase()
        self.yb.doConfigSetup()
        self.yb.doTsSetup()
        self.yb.doRpmDBSetup()
        yup = self.yb.doPackageLists(pkgnarrow='updates')
        if hasattr(self.yb.rpmdb, 'pkglist'):
            yinst = self.yb.rpmdb.pkglist
        else:
            yinst = self.yb.rpmdb.getPkgList()
        for dest, source in [(self.yum_avail, yup.updates),
                             (self.yum_installed, yinst)]:
            for pkg in source:
                if dest is self.yum_avail:
                    pname = pkg.name
                    data = {pkg.arch: (pkg.epoch, pkg.version, pkg.release)}
                else:
                    pname = pkg[0]
                    if pkg[1] is None:
                        a = 'noarch'
                    else:
                        a = pkg[1]
                    if pkg[2] is None:
                        e = '0'
                    else:
                        e = pkg[2]
                    data = {a: (e, pkg[3], pkg[4])}
                if pname in dest:
                    dest[pname].update(data)
                else:
                    dest[pname] = dict(data)

    def VerifyPackage(self, entry, modlist):
        pinned_version = None
        if entry.get('version', False) == 'auto':
            # old style entry; synthesize Instances from current installed
            if entry.get('name') not in self.yum_installed and \
                   entry.get('name') not in self.yum_avail:
                # new entry; fall back to default
                entry.set('version', 'any')
            else:
                data = copy.copy(self.yum_installed[entry.get('name')])
                if entry.get('name') in self.yum_avail:
                    # installed but out of date
                    data.update(self.yum_avail[entry.get('name')])
                for (arch, (epoch, vers, rel)) in list(data.items()):
                    x = Bcfg2.Client.XML.SubElement(entry, "Instance",
                                                    name=entry.get('name'),
                                                    version=vers, arch=arch,
                                                    release=rel, epoch=epoch)
                    if 'verify_flags' in entry.attrib:
                        x.set('verify_flags', entry.get('verify_flags'))
                    if 'verify' in entry.attrib:
                        x.set('verify', entry.get('verify'))

        if entry.get('type', False) == 'yum':
            # Check for virtual provides or packages.  If we don't have
            # this package use Yum to resolve it to a real package name
            knownPkgs = list(self.yum_installed.keys()) + list(self.yum_avail.keys())
            if entry.get('name') not in knownPkgs:
                # If the package name matches something installed
                # or available the that's the correct package.
                try:
                    pkgDict = dict([(i.name, i) for i in \
                                   self.yb.returnPackagesByDep(entry.get('name'))])
                except yum.Errors.YumBaseError:
                    e = sys.exc_info()[1]
                    self.logger.error('Yum Error Depsolving for %s: %s' % \
                                      (entry.get('name'), str(e)))
                    pkgDict = {}

                if len(pkgDict) > 1:
                    # What do we do with multiple packages?
                    s = "YUMng: returnPackagesByDep(%s) returned many packages"
                    self.logger.info(s % entry.get('name'))
                    s = "YUMng: matching packages: %s"
                    self.logger.info(s % str(list(pkgDict.keys())))
                    pkgs = set(pkgDict.keys()) & set(self.yum_installed.keys())
                    if len(pkgs) > 0:
                        # Virtual packages matches an installed real package
                        pkg = pkgDict[pkgs.pop()]
                        s = "YUMng: chosing: %s" % pkg.name
                        self.logger.info(s)
                    else:
                        # What's the right package?  This will fail verify
                        # and Yum should Do The Right Thing on package install
                        pkg = None
                elif len(pkgDict) == 1:
                    pkg = list(pkgDict.values())[0]
                else:  # len(pkgDict) == 0
                    s = "YUMng: returnPackagesByDep(%s) returned no results"
                    self.logger.info(s % entry.get('name'))
                    pkg = None

                if pkg is not None:
                    s = "YUMng: remapping virtual package %s to %s"
                    self.logger.info(s % (entry.get('name'), pkg.name))
                    entry.set('name', pkg.name)

        return Bcfg2.Client.Tools.RPMng.RPMng.VerifyPackage(self, entry,
                                                            modlist)

    def Install(self, packages, states):
        """
           Try and fix everything that RPMng.VerifyPackages() found wrong for
           each Package Entry.  This can result in individual RPMs being
           installed (for the first time), deleted, downgraded
           or upgraded.

           NOTE: YUM can not reinstall a package that it thinks is already
                 installed.

           packages is a list of Package Elements that has
               states[<Package Element>] == False

           The following effects occur:
           - states{} is conditionally updated for each package.
           - self.installed{} is rebuilt, possibly multiple times.
           - self.instance_status{} is conditionally updated for each instance
             of a package.
           - Each package will be added to self.modified[] if its states{}
             entry is set to True.

        """
        self.logger.info('Running YUMng.Install()')

        install_pkgs = []
        gpg_keys = []
        upgrade_pkgs = []

        # Remove extra instances.
        # Can not reverify because we don't have a package entry.
        if len(self.extra_instances) > 0:
            if (self.setup.get('remove') == 'all' or \
                self.setup.get('remove') == 'packages'):
                self.RemovePackages(self.extra_instances)
            else:
                self.logger.info("The following extra package instances will be removed by the '-r' option:")
                for pkg in self.extra_instances:
                    for inst in pkg:
                        self.logger.info("    %s %s" % \
                                         ((pkg.get('name'), self.str_evra(inst))))

        # Figure out which instances of the packages actually need something
        # doing to them and place in the appropriate work 'queue'.
        for pkg in packages:
            insts = [pinst for pinst in pkg \
                     if pinst.tag in ['Instance', 'Package']]
            if insts:
                for inst in insts:
                    if self.FixInstance(inst, self.instance_status[inst]):
                        if self.instance_status[inst].get('installed', False) \
                               == False:
                            if pkg.get('name') == 'gpg-pubkey':
                                gpg_keys.append(inst)
                            else:
                                install_pkgs.append(inst)
                        elif self.instance_status[inst].get('version_fail', \
                                                            False) == True:
                            upgrade_pkgs.append(inst)
            else:
                install_pkgs.append(pkg)

        # Install GPG keys.
        # Alternatively specify the required keys using 'gpgkey' in the
        # repository definition in yum.conf.  YUM will install the keys
        # automatically.
        if len(gpg_keys) > 0:
            for inst in gpg_keys:
                self.logger.info("Installing GPG keys.")
                if inst.get('simplefile') is None:
                    self.logger.error("GPG key has no simplefile attribute")
                    continue
                key_arg = os.path.join(self.instance_status[inst].get('pkg').get('uri'), \
                                       inst.get('simplefile'))
                cmdrc, output = self.cmd.run("rpm --import %s" % key_arg)
                if cmdrc != 0:
                    self.logger.debug("Unable to install %s-%s" % \
                                      (self.instance_status[inst].get('pkg').get('name'), \
                                       self.str_evra(inst)))
                else:
                    self.logger.debug("Installed %s-%s-%s" % \
                                      (self.instance_status[inst].get('pkg').get('name'), \
                                       inst.get('version'), inst.get('release')))
            self.RefreshPackages()
            self.gpg_keyids = self.getinstalledgpg()
            pkg = self.instance_status[gpg_keys[0]].get('pkg')
            states[pkg] = self.VerifyPackage(pkg, [])

        # Install packages.
        if len(install_pkgs) > 0:
            self.logger.info("Attempting to install packages")

            if YAD:
                pkgtool = "/usr/bin/yum -d0 -y install %s"
            else:
                pkgtool = "/usr/bin/yum -d0 install %s"

            install_args = []
            for inst in install_pkgs:
                pkg_arg = self.instance_status[inst].get('pkg').get('name')
                install_args.append(build_yname(pkg_arg, inst))

            cmdrc, output = self.cmd.run(pkgtool % " ".join(install_args))
            if cmdrc == 0:
                # The yum command succeeded.  All packages installed.
                self.logger.info("Single Pass for Install Succeeded")
                self.RefreshPackages()
            else:
                # The yum command failed.  No packages installed.
                # Try installing instances individually.
                self.logger.error("Single Pass Install of Packages Failed")
                installed_instances = []
                for inst in install_pkgs:
                    pkg_arg = build_yname(self.instance_status[inst].get('pkg').get('name'), inst)

                    cmdrc, output = self.cmd.run(pkgtool % pkg_arg)
                    if cmdrc == 0:
                        installed_instances.append(inst)
                    else:
                        self.logger.debug("%s %s would not install." % \
                                              (self.instance_status[inst].get('pkg').get('name'), \
                                               self.str_evra(inst)))
                self.RefreshPackages()

        # Fix upgradeable packages.
        if len(upgrade_pkgs) > 0:
            self.logger.info("Attempting to upgrade packages")

            if YAD:
                pkgtool = "/usr/bin/yum -d0 -y update %s"
            else:
                pkgtool = "/usr/bin/yum -d0 update %s"

            upgrade_args = []
            for inst in upgrade_pkgs:
                pkg_arg = build_yname(self.instance_status[inst].get('pkg').get('name'), inst)
                upgrade_args.append(pkg_arg)

            cmdrc, output = self.cmd.run(pkgtool % " ".join(upgrade_args))
            if cmdrc == 0:
                # The yum command succeeded.  All packages installed.
                self.logger.info("Single Pass for Install Succeeded")
                self.RefreshPackages()
            else:
                # The yum command failed.  No packages installed.
                # Try installing instances individually.
                self.logger.error("Single Pass Install of Packages Failed")
                installed_instances = []
                for inst in upgrade_pkgs:
                    pkg_arg = build_yname(self.instance_status[inst].get('pkg').get('name'), inst)
                    cmdrc, output = self.cmd.run(pkgtool % pkg_arg)
                    if cmdrc == 0:
                        installed_instances.append(inst)
                    else:
                        self.logger.debug("%s %s would not install." % \
                                              (self.instance_status[inst].get('pkg').get('name'), \
                                               self.str_evra(inst)))

                self.RefreshPackages()

        if not self.setup['kevlar']:
            for pkg_entry in [p for p in packages if self.canVerify(p)]:
                self.logger.debug("Reverifying Failed Package %s" % (pkg_entry.get('name')))
                states[pkg_entry] = self.VerifyPackage(pkg_entry, \
                                                       self.modlists.get(pkg_entry, []))

        for entry in [ent for ent in packages if states[ent]]:
            self.modified.append(entry)

    def RemovePackages(self, packages):
        """
           Remove specified entries.

           packages is a list of Package Entries with Instances generated
           by FindExtraPackages().
        """
        self.logger.debug('Running YUMng.RemovePackages()')

        if YAD:
            pkgtool = "/usr/bin/yum -d0 -y erase %s"
        else:
            pkgtool = "/usr/bin/yum -d0 erase %s"

        erase_args = []
        for pkg in packages:
            for inst in pkg:
                if pkg.get('name') != 'gpg-pubkey':
                    pkg_arg = pkg.get('name') + '-'
                    if inst.get('epoch', False):
                        pkg_arg = pkg_arg + inst.get('epoch') + ':'
                    pkg_arg = pkg_arg + inst.get('version') + '-' + inst.get('release')
                    if inst.get('arch', False):
                        pkg_arg = pkg_arg + '.' + inst.get('arch')
                    erase_args.append(pkg_arg)
                else:
                    pkgspec = {'name': pkg.get('name'),
                               'version': inst.get('version'),
                               'release': inst.get('release')}
                    self.logger.info("WARNING: gpg-pubkey package not in configuration %s %s"\
                                                 % (pkgspec.get('name'), self.str_evra(pkgspec)))
                    self.logger.info("         This package will be deleted in a future version of the RPMng driver.")

        cmdrc, output = self.cmd.run(pkgtool % " ".join(erase_args))
        if cmdrc == 0:
            self.modified += packages
            for pkg in erase_args:
                self.logger.info("Deleted %s" % (pkg))
        else:
            self.logger.info("Bulk erase failed with errors:")
            self.logger.debug("Erase results = %s" % output)
            self.logger.info("Attempting individual erase for each package.")
            for pkg in packages:
                pkg_modified = False
                for inst in pkg:
                    if pkg.get('name') != 'gpg-pubkey':
                        pkg_arg = pkg.get('name') + '-'
                        if 'epoch' in inst.attrib:
                            pkg_arg = pkg_arg + inst.get('epoch') + ':'
                        pkg_arg = pkg_arg + inst.get('version') + '-' + inst.get('release')
                        if 'arch' in inst.attrib:
                            pkg_arg = pkg_arg + '.' + inst.get('arch')
                    else:
                        self.logger.info("WARNING: gpg-pubkey package not in configuration %s %s"\
                                                 % (pkg.get('name'), self.str_evra(pkg)))
                        self.logger.info("         This package will be deleted in a future version of the RPMng driver.")
                        continue

                    cmdrc, output = self.cmd.run(self.pkgtool % pkg_arg)
                    if cmdrc == 0:
                        pkg_modified = True
                        self.logger.info("Deleted %s" % pkg_arg)
                    else:
                        self.logger.error("unable to delete %s" % pkg_arg)
                        self.logger.debug("Failure = %s" % output)
                if pkg_modified == True:
                    self.modified.append(pkg)

        self.RefreshPackages()
        self.extra = self.FindExtraPackages()
