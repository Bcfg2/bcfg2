'''This provides bcfg2 support for yum'''
__revision__ = '$Revision: $'

import Bcfg2.Client.Tools.RPMng, ConfigParser, sys, os.path

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

class YUMng(Bcfg2.Client.Tools.RPMng.RPMng):
    '''Support for Yum packages'''
    pkgtype = 'yum'

    __name__ = 'YUMng'
    __execs__ = ['/usr/bin/yum', '/var/lib/rpm']
    __handles__ = [('Package', 'yum'), ('Package', 'rpm')]
 
    __req__ = {'Package': ['name', 'version']}
    __ireq__ = {'Package': ['name']}
    #__ireq__ = {'Package': ['name', 'version']}
 
    __new_req__ = {'Package': ['name'], 'Instance': ['version', 'release', 'arch']}
    __new_ireq__ = {'Package': ['name'], \
                    'Instance': []}
    #__new_ireq__ = {'Package': ['name', 'uri'], \
    #                'Instance': ['simplefile', 'version', 'release', 'arch']}

    __gpg_req__ = {'Package': ['name', 'version']}
    __gpg_ireq__ = {'Package': ['name', 'version']}

    __new_gpg_req__ = {'Package': ['name'], 'Instance': ['version', 'release']}
    __new_gpg_ireq__ = {'Package': ['name'], 'Instance': ['version', 'release']}

    conflicts = ['RPMng']

    def Install(self, packages):
        '''
           Try and fix everything that RPMng.VerifyPackages() found wrong for
           each Package Entry.  This can result in individual RPMs being
           installed (for the first time), deleted, downgraded
           or upgraded. 

           NOTE: YUM can not reinstall a package that it thinks is already
                 installed.

           packages is a list of Package Elements that has
               self.states[<Package Element>] == False

           The following effects occur:
           - self.states{} is conditionally updated for each package.
           - self.installed{} is rebuilt, possibly multiple times.
           - self.instance_status{} is conditionally updated for each instance
             of a package.
           - Each package will be added to self.modified[] if its self.states{}
             entry is set to True.
        '''
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
                        self.logger.info("    %s %s", (pkg.get('name'), self.str_evra(inst)))

        # Figure out which instances of the packages actually need something
        # doing to them and place in the appropriate work 'queue'.
        for pkg in packages:
            for inst in [pinst for pinst in pkg \
                         if pinst.tag in ['Instance', 'Package']]:
                if self.FixInstance(inst, self.instance_status[inst]):
                    if self.instance_status[inst].get('installed', False) == False:
                        if pkg.get('name') == 'gpg-pubkey':
                            gpg_keys.append(inst)
                        else:
                            install_pkgs.append(inst)
                    elif self.instance_status[inst].get('version_fail', False) == True:
                        upgrade_pkgs.append(inst)

        # Install GPG keys.
        # Alternatively specify the required keys using 'gpgkey' in the 
        # repository definition in yum.conf.  YUM will install the keys 
        # automatically.
        if len(gpg_keys) > 0:
            for inst in gpg_keys:
                self.logger.info("Installing GPG keys.")
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
            self.states[pkg] = self.VerifyPackage(pkg, [])

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
                if inst.get('epoch', False):
                    pkg_arg = pkg_arg + '-' + inst.get('epoch') + ':' + inst.get('version') + \
                              '-' + inst.get('release') + '.' + inst.get('arch')
                else:
                    if inst.get('version', False):
                        pkg_arg = pkg_arg + '-' + inst.get('version')
                        if inst.get('release', False):
                            pkg_arg = pkg_arg + '-' + inst.get('release')
                    if inst.get('arch', False):
                        pkg_arg = pkg_arg + '.' + inst.get('arch')
                install_args.append(pkg_arg)
            
            cmdrc, output = self.cmd.run(pkgtool % " ".join(install_args))
            if cmdrc == 0:
                # The yum command succeeded.  All packages installed.
                self.logger.info("Single Pass for Install Succeded")
                self.RefreshPackages()
            else:
                # The yum command failed.  No packages installed.
                # Try installing instances individually.
                self.logger.error("Single Pass Install of Packages Failed")
                installed_instances = []
                for inst in install_pkgs:
                    pkg_arg = self.instance_status[inst].get('pkg').get('name')
                    if inst.get('epoch', False):
                        pkg_arg = pkg_arg + '-' + inst.get('epoch') + ':' + inst.get('version') + \
                                  '-' + inst.get('release') + '.' + inst.get('arch')
                    else:
                        if inst.get('version', False):
                            pkg_arg = pkg_arg + '-' + inst.get('version')
                            if inst.get('release', False):
                                pkg_arg = pkg_arg + '-' + inst.get('release')
                        if inst.get('arch', False):
                            pkg_arg = pkg_arg + '.' + inst.get('arch')
    
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
                pkg_arg = self.instance_status[inst].get('pkg').get('name')
                if inst.get('epoch', False):
                    pkg_arg = pkg_arg + '-' + inst.get('epoch') + ':' + inst.get('version') + \
                              '-' + inst.get('release') + '.' + inst.get('arch')
                else:
                    if inst.get('version', False):
                        pkg_arg = pkg_arg + '-' + inst.get('version')
                        if inst.get('release', False):
                            pkg_arg = pkg_arg + '-' + inst.get('release')
                    if inst.get('arch', False):
                        pkg_arg = pkg_arg + '.' + inst.get('arch')
                upgrade_args.append(pkg_arg)
            
            cmdrc, output = self.cmd.run(pkgtool % " ".join(upgrade_args))
            if cmdrc == 0:
                # The yum command succeeded.  All packages installed.
                self.logger.info("Single Pass for Install Succeded")
                self.RefreshPackages()
            else:
                # The yum command failed.  No packages installed.
                # Try installing instances individually.
                self.logger.error("Single Pass Install of Packages Failed")
                installed_instances = []
                for inst in upgrade_pkgs:
                    pkg_arg = self.instance_status[inst].get('pkg').get('name')
                    if inst.get('epoch', False):
                        pkg_arg = pkg_arg + '-' + inst.get('epoch') + ':' + inst.get('version') + \
                                  '-' + inst.get('release') + '.' + inst.get('arch')
                    else:
                        if inst.get('version', False):
                            pkg_arg = pkg_arg + '-' + inst.get('version')
                            if inst.get('release', False):
                                pkg_arg = pkg_arg + '-' + inst.get('release')
                        if inst.get('arch', False):
                            pkg_arg = pkg_arg + '.' + inst.get('arch')
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
                self.states[pkg_entry] = self.VerifyPackage(pkg_entry, \
                                                                 self.modlists.get(pkg_entry, []))

        for entry in [ent for ent in packages if self.states[ent]]:
            self.modified.append(entry)

    def RemovePackages(self, packages):
        '''
           Remove specified entries.

           packages is a list of Package Entries with Instances generated
           by FindExtraPackages().
        '''
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
                    pkgspec = { 'name':pkg.get('name'),
                            'version':inst.get('version'),
                            'release':inst.get('release')}
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
                        if inst.haskey('epoch'):
                            pkg_arg = pkg_arg + inst.get('epoch') + ':'
                        pkg_arg = pkg_arg + inst.get('version') + '-' + inst.get('release')
                        if inst.haskey('arch'):
                            pkg_arg = pkg_arg + '.' + inst.get('arch')
                    else:
                        self.logger.info("WARNING: gpg-pubkey package not in configuration %s %s"\
                                                 % (pkg.get('name'), self.str_evra(pkg)))
                        self.logger.info("         This package will be deleted in a future version of the RPMng driver.")

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
