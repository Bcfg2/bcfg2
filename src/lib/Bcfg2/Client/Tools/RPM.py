"""Bcfg2 Support for RPMS"""

import os.path
import rpm
import rpmtools
import Bcfg2.Client.Tools

class RPM(Bcfg2.Client.Tools.PkgTool):
    """Support for RPM packages."""
    __execs__ = ['/bin/rpm', '/var/lib/rpm']
    __handles__ = [('Package', 'rpm')]

    __req__ = {'Package': ['name', 'version']}
    __ireq__ = {'Package': ['url']}

    __new_req__ = {'Package': ['name'],
                   'Instance': ['version', 'release', 'arch']}
    __new_ireq__ = {'Package': ['uri'], \
                    'Instance': ['simplefile']}

    __gpg_req__ = {'Package': ['name', 'version']}
    __gpg_ireq__ = {'Package': ['name', 'version']}

    __new_gpg_req__ = {'Package': ['name'],
                       'Instance': ['version', 'release']}
    __new_gpg_ireq__ = {'Package': ['name'],
                        'Instance': ['version', 'release']}

    conflicts = ['RPMng']

    pkgtype = 'rpm'
    pkgtool = ("rpm --oldpackage --replacepkgs --quiet -U %s", ("%s", ["url"]))

    def __init__(self, logger, setup, config):
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, setup, config)

        # create a global ignore list used when ignoring particular
        # files during package verification
        self.ignores = [entry.get('name') for struct in config for entry in struct \
                        if entry.get('type') == 'ignore']
        self.instance_status = {}
        self.extra_instances = []
        self.modlists = {}
        self.gpg_keyids = self.getinstalledgpg()

        opt_prefix = self.name.lower()
        self.installOnlyPkgs = self.setup["%s_installonly" % opt_prefix]
        if 'gpg-pubkey' not in self.installOnlyPkgs:
            self.installOnlyPkgs.append('gpg-pubkey')
        self.erase_flags = self.setup['%s_erase_flags' % opt_prefix]
        self.pkg_checks = self.setup['%s_pkg_checks' % opt_prefix]
        self.pkg_verify = self.setup['%s_pkg_verify' % opt_prefix]
        self.installed_action = self.setup['%s_installed_action' % opt_prefix]
        self.version_fail_action = self.setup['%s_version_fail_action' %
                                              opt_prefix]
        self.verify_fail_action = self.setup['%s_verify_fail_action' %
                                             opt_prefix]
        self.verify_flags = self.setup['%s_verify_flags' % opt_prefix]
        if '' in self.verify_flags:
            self.verify_flags.remove('')

        self.logger.debug('%s: installOnlyPackages = %s' %
                          (self.name, self.installOnlyPkgs))
        self.logger.debug('%s: erase_flags = %s' %
                          (self.name, self.erase_flags))
        self.logger.debug('%s: pkg_checks = %s' %
                          (self.name, self.pkg_checks))
        self.logger.debug('%s: pkg_verify = %s' %
                          (self.name, self.pkg_verify))
        self.logger.debug('%s: installed_action = %s' %
                          (self.name, self.installed_action))
        self.logger.debug('%s: version_fail_action = %s' %
                          (self.name, self.version_fail_action))
        self.logger.debug('%s: verify_fail_action = %s' %
                          (self.name, self.verify_fail_action))
        self.logger.debug('%s: verify_flags = %s' %
                          (self.name, self.verify_flags))

        # Force a re- prelink of all packages if prelink exists.
        # Many, if not most package verifies can be caused by out of
        # date prelinking.
        if os.path.isfile('/usr/sbin/prelink') and not self.setup['dryrun']:
            rv = self.cmd.run('/usr/sbin/prelink -a -mR')
            if rv.success:
                self.logger.debug('Pre-emptive prelink succeeded')
            else:
                # FIXME : this is dumb - what if the output is huge?
                self.logger.error('Pre-emptive prelink failed: %s' % rv.error)

    def RefreshPackages(self):
        """
            Creates self.installed{} which is a dict of installed packages.

            The dict items are lists of nevra dicts.  This loosely matches the
            config from the server and what rpmtools uses to specify pacakges.

            e.g.

            self.installed['foo'] = [ {'name':'foo', 'epoch':None,
                                       'version':'1', 'release':2,
                                       'arch':'i386'},
                                      {'name':'foo', 'epoch':None,
                                       'version':'1', 'release':2,
                                       'arch':'x86_64'} ]
        """
        self.installed = {}
        refresh_ts = rpmtools.rpmtransactionset()
        # Don't bother with signature checks at this stage. The GPG keys might
        # not be installed.
        refresh_ts.setVSFlags(rpm._RPMVSF_NODIGESTS|rpm._RPMVSF_NOSIGNATURES)
        for nevra in rpmtools.rpmpackagelist(refresh_ts):
            self.installed.setdefault(nevra['name'], []).append(nevra)
        if self.setup['debug']:
            print("The following package instances are installed:")
            for name, instances in list(self.installed.items()):
                self.logger.debug("    " + name)
                for inst in instances:
                    self.logger.debug("        %s" %self.str_evra(inst))
        refresh_ts.closeDB()
        del refresh_ts

    def VerifyPackage(self, entry, modlist, pinned_version=None):
        """
            Verify Package status for entry.
            Performs the following:
                - Checks for the presence of required Package Instances.
                - Compares the evra 'version' info against self.installed{}.
                - RPM level package verify (rpm --verify).
                - Checks for the presence of unrequired package instances.

            Produces the following dict and list for RPM.Install() to use:
              For installs/upgrades/fixes of required instances:
                instance_status = { <Instance Element Object>:
                                       { 'installed': True|False,
                                         'version_fail': True|False,
                                         'verify_fail': True|False,
                                         'pkg': <Package Element Object>,
                                         'modlist': [ <filename>, ... ],
                                         'verify' : [ <rpm --verify results> ]
                                       }, ......
                                  }

              For deletions of unrequired instances:
                extra_instances = [ <Package Element Object>, ..... ]

              Constructs the text prompts for interactive mode.
        """
        instances = [inst for inst in entry if inst.tag == 'Instance' or inst.tag == 'Package']
        if instances == []:
            # We have an old style no Instance entry. Convert it to new style.
            instance = Bcfg2.Client.XML.SubElement(entry, 'Package')
            for attrib in list(entry.attrib.keys()):
                instance.attrib[attrib] = entry.attrib[attrib]
            if (self.pkg_checks and
                entry.get('pkg_checks', 'true').lower() == 'true'):
                if 'any' in [entry.get('version'), pinned_version]:
                    version, release = 'any', 'any'
                elif entry.get('version') == 'auto':
                    if pinned_version != None:
                        version, release = pinned_version.split('-')
                    else:
                        return False
                else:
                    version, release = entry.get('version').split('-')
                instance.set('version', version)
                instance.set('release', release)
                if entry.get('verify', 'true') == 'false':
                    instance.set('verify', 'false')
            instances = [ instance ]

        self.logger.debug("Verifying package instances for %s" % entry.get('name'))
        package_fail = False
        qtext_versions = ''

        if entry.get('name') in self.installed:
            # There is at least one instance installed.
            if (self.pkg_checks and
                entry.get('pkg_checks', 'true').lower() == 'true'):
                rpmTs = rpm.TransactionSet()
                rpmHeader = None
                for h in rpmTs.dbMatch(rpm.RPMTAG_NAME, entry.get('name')):
                    if rpmHeader is None or rpm.versionCompare(h, rpmHeader) > 0:
                        rpmHeader = h
                rpmProvides = [ h['provides'] for h in \
                            rpmTs.dbMatch(rpm.RPMTAG_NAME, entry.get('name')) ]
                rpmIntersection = set(rpmHeader['provides']) & \
                                  set(self.installOnlyPkgs)
                if len(rpmIntersection) > 0:
                    # Packages that should only be installed or removed.
                    # e.g. kernels.
                    self.logger.debug("        Install only package.")
                    for inst in instances:
                        self.instance_status.setdefault(inst, {})['installed'] = False
                        self.instance_status[inst]['version_fail'] = False
                        if inst.tag == 'Package' and len(self.installed[entry.get('name')]) > 1:
                            self.logger.error("WARNING: Multiple instances of package %s are installed." % \
                                              (entry.get('name')))
                        for pkg in self.installed[entry.get('name')]:
                            if inst.get('version') == 'any' or self.pkg_vr_equal(inst, pkg) \
                               or self.inst_evra_equal(inst, pkg):
                                if inst.get('version') == 'any':
                                    self.logger.error("got any version")
                                self.logger.debug("        %s" % self.str_evra(inst))
                                self.instance_status[inst]['installed'] = True

                                if (self.pkg_verify and
                                    inst.get('pkg_verify', 'true').lower() == 'true'):
                                    flags = inst.get('verify_flags', '').split(',') + self.verify_flags
                                    if pkg.get('gpgkeyid', '')[-8:] not in self.gpg_keyids and \
                                       entry.get('name') != 'gpg-pubkey':
                                        flags += ['nosignature', 'nodigest']
                                        self.logger.debug('WARNING: Package %s %s requires GPG Public key with ID %s'\
                                                           % (pkg.get('name'), self.str_evra(pkg), \
                                                              pkg.get('gpgkeyid', '')))
                                        self.logger.debug('         Disabling signature check.')

                                    if self.setup.get('quick', False):
                                        if rpmtools.prelink_exists:
                                            flags += ['nomd5', 'nosize']
                                        else:
                                            flags += ['nomd5']
                                    self.logger.debug("        verify_flags = %s" % flags)

                                    if inst.get('verify', 'true') == 'false':
                                        self.instance_status[inst]['verify'] = None
                                    else:
                                        vp_ts = rpmtools.rpmtransactionset()
                                        self.instance_status[inst]['verify'] = \
                                                                             rpmtools.rpm_verify( vp_ts, pkg, flags)
                                        vp_ts.closeDB()
                                        del vp_ts

                        if self.instance_status[inst]['installed'] == False:
                            self.logger.info("        Package %s %s not installed." % \
                                         (entry.get('name'), self.str_evra(inst)))

                            qtext_versions = qtext_versions + 'I(%s) ' % self.str_evra(inst)
                            entry.set('current_exists', 'false')
                else:
                    # Normal Packages that can be upgraded.
                    for inst in instances:
                        self.instance_status.setdefault(inst, {})['installed'] = False
                        self.instance_status[inst]['version_fail'] = False

                        # Only installed packages with the same architecture are
                        # relevant.
                        if inst.get('arch', None) == None:
                            arch_match = self.installed[entry.get('name')]
                        else:
                            arch_match = [pkg for pkg in self.installed[entry.get('name')] \
                                              if pkg.get('arch', None) == inst.get('arch', None)]

                        if len(arch_match) > 1:
                            self.logger.error("Multiple instances of package %s installed with the same achitecture." % \
                                                  (entry.get('name')))
                        elif len(arch_match) == 1:
                            # There is only one installed like there should be.
                            # Check that it is the right version.
                            for pkg in arch_match:
                                if inst.get('version') == 'any' or self.pkg_vr_equal(inst, pkg) or \
                                       self.inst_evra_equal(inst, pkg):
                                    self.logger.debug("        %s" % self.str_evra(inst))
                                    self.instance_status[inst]['installed'] = True

                                    if (self.pkg_verify and
                                        inst.get('pkg_verify', 'true').lower() == 'true'):
                                        flags = inst.get('verify_flags', '').split(',') + self.verify_flags
                                        if pkg.get('gpgkeyid', '')[-8:] not in self.gpg_keyids and \
                                           'nosignature' not in flags:
                                            flags += ['nosignature', 'nodigest']
                                            self.logger.info('WARNING: Package %s %s requires GPG Public key with ID %s'\
                                                         % (pkg.get('name'), self.str_evra(pkg), \
                                                            pkg.get('gpgkeyid', '')))
                                            self.logger.info('         Disabling signature check.')

                                        if self.setup.get('quick', False):
                                            if rpmtools.prelink_exists:
                                                flags += ['nomd5', 'nosize']
                                            else:
                                                flags += ['nomd5']
                                        self.logger.debug("        verify_flags = %s" % flags)

                                        if inst.get('verify', 'true') == 'false':
                                            self.instance_status[inst]['verify'] = None
                                        else:
                                            vp_ts = rpmtools.rpmtransactionset()
                                            self.instance_status[inst]['verify'] = \
                                                                                 rpmtools.rpm_verify( vp_ts, pkg, flags )
                                            vp_ts.closeDB()
                                            del vp_ts

                                else:
                                    # Wrong version installed.
                                    self.instance_status[inst]['version_fail'] = True
                                    self.logger.info("        Wrong version installed.  Want %s, but have %s"\
                                                    % (self.str_evra(inst), self.str_evra(pkg)))

                                    qtext_versions = qtext_versions + 'U(%s -> %s) ' % \
                                                          (self.str_evra(pkg), self.str_evra(inst))
                        elif len(arch_match) == 0:
                            # This instance is not installed.
                            self.instance_status[inst]['installed'] = False
                            self.logger.info("        %s is not installed." % self.str_evra(inst))
                            qtext_versions = qtext_versions + 'I(%s) ' % self.str_evra(inst)

                # Check the rpm verify results.
                for inst in instances:
                    instance_fail = False
                    # Dump the rpm verify results.
                    #****Write something to format this nicely.*****
                    if self.setup['debug'] and self.instance_status[inst].get('verify', None):
                        self.logger.debug(self.instance_status[inst]['verify'])

                    self.instance_status[inst]['verify_fail'] = False
                    if self.instance_status[inst].get('verify', None):
                        if len(self.instance_status[inst].get('verify')) > 1:
                            self.logger.info("WARNING: Verification of more than one package instance.")

                        for result in self.instance_status[inst]['verify']:

                            # Check header results
                            if result.get('hdr', None):
                                instance_fail = True
                                self.instance_status[inst]['verify_fail'] = True

                            # Check dependency results
                            if result.get('deps', None):
                                instance_fail = True
                                self.instance_status[inst]['verify_fail'] = True

                            # Check the rpm verify file results against the modlist
                            # and entry and per Instance Ignores.
                            ignores = [ig.get('name') for ig in entry.findall('Ignore')] + \
                                      [ig.get('name') for ig in inst.findall('Ignore')] + \
                                      self.ignores
                            for file_result in result.get('files', []):
                                if file_result[-1] not in modlist + ignores:
                                    instance_fail = True
                                    self.instance_status[inst]['verify_fail'] = True
                                else:
                                    self.logger.debug("        Modlist/Ignore match: %s" % \
                                                                                 (file_result[-1]))

                        if instance_fail == True:
                            self.logger.debug("*** Instance %s failed RPM verification ***" % \
                                              self.str_evra(inst))
                            qtext_versions = qtext_versions + 'R(%s) ' % self.str_evra(inst)
                            self.modlists[entry] = modlist

                            # Attach status structure for return to server for reporting.
                            inst.set('verify_status', str(self.instance_status[inst]))

                    if self.instance_status[inst]['installed'] == False or \
                       self.instance_status[inst].get('version_fail', False)== True or \
                       self.instance_status[inst].get('verify_fail', False) == True:
                        package_fail = True
                        self.instance_status[inst]['pkg'] = entry
                        self.modlists[entry] = modlist

                # Find Installed Instances that are not in the Config.
                extra_installed = self.FindExtraInstances(entry, self.installed[entry.get('name')])
                if extra_installed != None:
                    package_fail = True
                    self.extra_instances.append(extra_installed)
                    for inst in extra_installed.findall('Instance'):
                        qtext_versions = qtext_versions + 'D(%s) ' % self.str_evra(inst)
                    self.logger.debug("Found Extra Instances %s" % qtext_versions)

                if package_fail == True:
                    self.logger.info("        Package %s failed verification." % \
                                                              (entry.get('name')))
                    qtext = 'Install/Upgrade/delete Package %s instance(s) - %s (y/N) ' % \
                                                  (entry.get('name'), qtext_versions)
                    entry.set('qtext', qtext)

                    bcfg2_versions = ''
                    for bcfg2_inst in [inst for inst in instances if inst.tag == 'Instance']:
                        bcfg2_versions = bcfg2_versions + '(%s) ' % self.str_evra(bcfg2_inst)
                    if bcfg2_versions != '':
                        entry.set('version', bcfg2_versions)
                    installed_versions = ''

                    for installed_inst in self.installed[entry.get('name')]:
                        installed_versions = installed_versions + '(%s) ' % \
                                                                      self.str_evra(installed_inst)

                    entry.set('current_version', installed_versions)
                    return False

        else:
            # There are no Instances of this package installed.
            self.logger.debug("Package %s has no instances installed" % (entry.get('name')))
            entry.set('current_exists', 'false')
            bcfg2_versions = ''
            for inst in instances:
                qtext_versions = qtext_versions + 'I(%s) ' % self.str_evra(inst)
                self.instance_status.setdefault(inst, {})['installed'] = False
                self.modlists[entry] = modlist
                self.instance_status[inst]['pkg'] = entry
                if inst.tag == 'Instance':
                    bcfg2_versions = bcfg2_versions + '(%s) ' % self.str_evra(inst)
            if bcfg2_versions != '':
                entry.set('version', bcfg2_versions)
            entry.set('qtext', "Install Package %s Instance(s) %s? (y/N) " % \
                      (entry.get('name'), qtext_versions))

            return False
        return True

    def Remove(self, packages):
        """
           Remove specified entries.

           packages is a list of Package Entries with Instances generated
           by FindExtra().

        """
        self.logger.debug('Running RPM.Remove()')

        pkgspec_list = []
        for pkg in packages:
            for inst in pkg:
                if pkg.get('name') != 'gpg-pubkey':
                    pkgspec = { 'name':pkg.get('name'),
                            'epoch':inst.get('epoch', None),
                            'version':inst.get('version'),
                            'release':inst.get('release'),
                            'arch':inst.get('arch') }
                    pkgspec_list.append(pkgspec)
                else:
                    pkgspec = { 'name':pkg.get('name'),
                            'version':inst.get('version'),
                            'release':inst.get('release')}
                    self.logger.info("WARNING: gpg-pubkey package not in configuration %s %s"\
                                                 % (pkgspec.get('name'), self.str_evra(pkgspec)))
                    self.logger.info("         This package will be deleted in a future version of the RPM driver.")
                #pkgspec_list.append(pkg_spec)

        erase_results = rpmtools.rpm_erase(pkgspec_list, self.erase_flags)
        if erase_results == []:
            self.modified += packages
            for pkg in pkgspec_list:
                self.logger.info("Deleted %s %s" % (pkg.get('name'), self.str_evra(pkg)))
        else:
            self.logger.info("Bulk erase failed with errors:")
            self.logger.debug("Erase results = %s" % erase_results)
            self.logger.info("Attempting individual erase for each package.")
            pkgspec_list = []
            for pkg in packages:
                pkg_modified = False
                for inst in pkg:
                    if pkg.get('name') != 'gpg-pubkey':
                        pkgspec = { 'name':pkg.get('name'),
                                'epoch':inst.get('epoch', None),
                                'version':inst.get('version'),
                                'release':inst.get('release'),
                                'arch':inst.get('arch') }
                        pkgspec_list.append(pkgspec)
                    else:
                        pkgspec = { 'name':pkg.get('name'),
                                'version':inst.get('version'),
                                'release':inst.get('release')}
                        self.logger.info("WARNING: gpg-pubkey package not in configuration %s %s"\
                                                   % (pkgspec.get('name'), self.str_evra(pkgspec)))
                        self.logger.info("         This package will be deleted in a future version of the RPM driver.")
                        continue # Don't delete the gpg-pubkey packages for now.
                    erase_results = rpmtools.rpm_erase([pkgspec], self.erase_flags)
                    if erase_results == []:
                        pkg_modified = True
                        self.logger.info("Deleted %s %s" % \
                                                   (pkgspec.get('name'), self.str_evra(pkgspec)))
                    else:
                        self.logger.error("unable to delete %s %s" % \
                                                   (pkgspec.get('name'), self.str_evra(pkgspec)))
                        self.logger.debug("Failure = %s" % erase_results)
                if pkg_modified == True:
                    self.modified.append(pkg)

        self.RefreshPackages()
        self.extra = self.FindExtra()

    def FixInstance(self, instance, inst_status):
        """
           Control if a reinstall of a package happens or not based on the
           results from RPM.VerifyPackage().

           Return True to reinstall, False to not reintstall.

        """
        fix = False

        if inst_status.get('installed', False) == False:
            if instance.get('installed_action', 'install') == "install" and \
               self.installed_action == "install":
                fix = True
            else:
                self.logger.debug('Installed Action for %s %s is to not install' % \
                                  (inst_status.get('pkg').get('name'),
                                   self.str_evra(instance)))

        elif inst_status.get('version_fail', False) == True:
            if instance.get('version_fail_action', 'upgrade') == "upgrade" and \
                self.version_fail_action == "upgrade":
                fix = True
            else:
                self.logger.debug('Version Fail Action for %s %s is to not upgrade' % \
                                  (inst_status.get('pkg').get('name'),
                                   self.str_evra(instance)))

        elif inst_status.get('verify_fail', False) == True and self.name == "RPM":
            # yum can't reinstall packages so only do this for rpm.
            if instance.get('verify_fail_action', 'reinstall') == "reinstall" and \
               self.verify_fail_action == "reinstall":
                for inst in inst_status.get('verify'):
                    # This needs to be a for loop rather than a straight get()
                    # because the underlying routines handle multiple packages
                    # and return a list of results.
                    self.logger.debug('reinstall_check: %s %s:%s-%s.%s' % inst.get('nevra'))

                    if inst.get("hdr", False):
                        fix = True

                    elif inst.get('files', False):
                        # Parse rpm verify file results
                        for file_result in inst.get('files', []):
                            self.logger.debug('reinstall_check: file: %s' % file_result)
                            if file_result[-2] != 'c':
                                fix = True
                                break

                    # Shouldn't really need this, but included for clarity.
                    elif inst.get("deps", False):
                        fix = False
            else:
                self.logger.debug('Verify Fail Action for %s %s is to not reinstall' % \
                                                     (inst_status.get('pkg').get('name'),
                                                      self.str_evra(instance)))

        return fix

    def Install(self, packages, states):
        """
           Try and fix everything that RPM.VerifyPackages() found wrong for
           each Package Entry.  This can result in individual RPMs being
           installed (for the first time), reinstalled, deleted, downgraded
           or upgraded.

           packages is a list of Package Elements that has
               states[<Package Element>] == False

           The following effects occur:
           - states{} is conditionally updated for each package.
           - self.installed{} is rebuilt, possibly multiple times.
           - self.instance_statusi{} is conditionally updated for each instance
             of a package.
           - Each package will be added to self.modified[] if its states{}
             entry is set to True.

        """
        self.logger.info('Runing RPM.Install()')

        install_only_pkgs = []
        gpg_keys = []
        upgrade_pkgs = []

        # Remove extra instances.
        # Can not reverify because we don't have a package entry.
        if len(self.extra_instances) > 0:
            if (self.setup.get('remove') == 'all' or \
                self.setup.get('remove') == 'packages') and\
                not self.setup.get('dryrun'):
                self.Remove(self.extra_instances)
            else:
                self.logger.info("The following extra package instances will be removed by the '-r' option:")
                for pkg in self.extra_instances:
                    for inst in pkg:
                        self.logger.info("    %s %s" % (pkg.get('name'), self.str_evra(inst)))

        # Figure out which instances of the packages actually need something
        # doing to them and place in the appropriate work 'queue'.
        for pkg in packages:
            for inst in [instn for instn in pkg if instn.tag \
                         in ['Instance', 'Package']]:
                if self.FixInstance(inst, self.instance_status[inst]):
                    if pkg.get('name') == 'gpg-pubkey':
                        gpg_keys.append(inst)
                    elif pkg.get('name') in self.installOnlyPkgs:
                        install_only_pkgs.append(inst)
                    else:
                        upgrade_pkgs.append(inst)

        # Fix installOnlyPackages
        if len(install_only_pkgs) > 0:
            self.logger.info("Attempting to install 'install only packages'")
            install_args = \
                " ".join(os.path.join(self.instance_status[inst].get('pkg').get('uri'),
                                      inst.get('simplefile'))
                         for inst in install_only_pkgs)
            if self.cmd.run("rpm --install --quiet --oldpackage --replacepkgs "
                            "%s" % install_args):
                # The rpm command succeeded.  All packages installed.
                self.logger.info("Single Pass for InstallOnlyPkgs Succeded")
                self.RefreshPackages()
            else:
                # The rpm command failed.  No packages installed.
                # Try installing instances individually.
                self.logger.error("Single Pass for InstallOnlyPackages Failed")
                installed_instances = []
                for inst in install_only_pkgs:
                    install_args = \
                        os.path.join(self.instance_status[inst].get('pkg').get('uri'),
                                     inst.get('simplefile'))
                    if self.cmd.run("rpm --install --quiet --oldpackage "
                                    "--replacepkgs %s" % install_args):
                        installed_instances.append(inst)
                    else:
                        self.logger.debug("InstallOnlyPackage %s %s would not install." % \
                                              (self.instance_status[inst].get('pkg').get('name'), \
                                               self.str_evra(inst)))

                install_pkg_set = set([self.instance_status[inst].get('pkg') \
                                                      for inst in install_only_pkgs])
                self.RefreshPackages()

        # Install GPG keys.
        if len(gpg_keys) > 0:
            for inst in gpg_keys:
                self.logger.info("Installing GPG keys.")
                key_arg = os.path.join(self.instance_status[inst].get('pkg').get('uri'), \
                                                     inst.get('simplefile'))
                if not self.cmd.run("rpm --import %s" % key_arg):
                    self.logger.debug("Unable to install %s-%s" %
                                      (self.instance_status[inst].get('pkg').get('name'),
                                       self.str_evra(inst)))
                else:
                    self.logger.debug("Installed %s-%s-%s" %
                                      (self.instance_status[inst].get('pkg').get('name'),
                                       inst.get('version'),
                                       inst.get('release')))
            self.RefreshPackages()
            self.gpg_keyids = self.getinstalledgpg()
            pkg = self.instance_status[gpg_keys[0]].get('pkg')
            states[pkg] = self.VerifyPackage(pkg, [])

        # Fix upgradeable packages.
        if len(upgrade_pkgs) > 0:
            self.logger.info("Attempting to upgrade packages")
            upgrade_args = " ".join([os.path.join(self.instance_status[inst].get('pkg').get('uri'), \
                                                  inst.get('simplefile')) \
                                           for inst in upgrade_pkgs])
            if self.cmd.run("rpm --upgrade --quiet --oldpackage --replacepkgs "
                            "%s" % upgrade_args):
                # The rpm command succeeded.  All packages upgraded.
                self.logger.info("Single Pass for Upgraded Packages Succeded")
                upgrade_pkg_set = set([self.instance_status[inst].get('pkg')
                                       for inst in upgrade_pkgs])
                self.RefreshPackages()
            else:
                # The rpm command failed.  No packages upgraded.
                # Try upgrading instances individually.
                self.logger.error("Single Pass for Upgrading Packages Failed")
                upgraded_instances = []
                for inst in upgrade_pkgs:
                    upgrade_args = os.path.join(self.instance_status[inst].get('pkg').get('uri'), \
                                                     inst.get('simplefile'))
                    #self.logger.debug("rpm --upgrade --quiet --oldpackage --replacepkgs %s" % \
                    #                                                      upgrade_args)
                    if self.cmd.run("rpm --upgrade --quiet --oldpackage "
                                    "--replacepkgs %s" % upgrade_args):
                        upgraded_instances.append(inst)
                    else:
                        self.logger.debug("Package %s %s would not upgrade." %
                                          (self.instance_status[inst].get('pkg').get('name'),
                                           self.str_evra(inst)))

                upgrade_pkg_set = set([self.instance_status[inst].get('pkg') \
                                                      for inst in upgrade_pkgs])
                self.RefreshPackages()

        if not self.setup['kevlar']:
            for pkg_entry in packages:
                self.logger.debug("Reverifying Failed Package %s" % (pkg_entry.get('name')))
                states[pkg_entry] = self.VerifyPackage(pkg_entry, \
                                                       self.modlists.get(pkg_entry, []))

        for entry in [ent for ent in packages if states[ent]]:
            self.modified.append(entry)

    def canInstall(self, entry):
        """Test if entry has enough information to be installed."""
        if not self.handlesEntry(entry):
            return False

        if 'failure' in entry.attrib:
            self.logger.error("Cannot install entry %s:%s with bind failure" % \
                              (entry.tag, entry.get('name')))
            return False


        instances = entry.findall('Instance')

        # If the entry wasn't verifiable, then we really don't want to try and fix something
        # that we don't know is broken.
        if not self.canVerify(entry):
            self.logger.debug("WARNING: Package %s was not verifiable, not passing to Install()" \
                                           % entry.get('name'))
            return False

        if not instances:
            # Old non Instance format, unmodified.
            if entry.get('name') == 'gpg-pubkey':
                # gpg-pubkey packages aren't really pacakges, so we have to do
                # something a little different.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__gpg_ireq__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot install" \
                                      % (entry.tag, entry.get('name')))
                    return False
            else:
                if [attr for attr in self.__ireq__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot install" \
                                      % (entry.tag, entry.get('name')))
                    return False
        else:
            if entry.get('name') == 'gpg-pubkey':
                # gpg-pubkey packages aren't really pacakges, so we have to do
                # something a little different.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__new_gpg_ireq__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot install" \
                                      % (entry.tag, entry.get('name')))
                    return False
                # Check that the Instance Level has what we need for verification.
                for inst in instances:
                    if [attr for attr in self.__new_gpg_ireq__[inst.tag] \
                                 if attr not in inst.attrib]:
                        self.logger.error("Incomplete information for entry %s:%s; cannot install"\
                                          % (inst.tag, entry.get('name')))
                        return False
            else:
                # New format with Instances.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__new_ireq__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot install" \
                                      % (entry.tag, entry.get('name')))
                    self.logger.error("             Required attributes that may not be present are %s" \
                                      % (self.__new_ireq__[entry.tag]))
                    return False
                # Check that the Instance Level has what we need for verification.
                for inst in instances:
                    if inst.tag == 'Instance':
                        if [attr for attr in self.__new_ireq__[inst.tag] \
                                     if attr not in inst.attrib]:
                            self.logger.error("Incomplete information for %s of package %s; cannot install" \
                                              % (inst.tag, entry.get('name')))
                            self.logger.error("         Required attributes that may not be present are %s" \
                                              % (self.__new_ireq__[inst.tag]))
                            return False
        return True

    def canVerify(self, entry):
        """
            Test if entry has enough information to be verified.

            Three types of entries are checked.
               Old style Package
               New style Package with Instances
               pgp-pubkey packages

           Also the old style entries get modified after the first
           VerifyPackage() run, so there needs to be a second test.

        """
        if not self.handlesEntry(entry):
            return False

        if 'failure' in entry.attrib:
            self.logger.error("Entry %s:%s reports bind failure: %s" % \
                              (entry.tag, entry.get('name'), entry.get('failure')))
            return False

        # We don't want to do any checks so we don't care what the entry has in it.
        if (not self.pkg_checks or
            entry.get('pkg_checks', 'true').lower() == 'false'):
            return True

        instances = entry.findall('Instance')

        if not instances:
            # Old non Instance format, unmodified.
            if entry.get('name') == 'gpg-pubkey':
                # gpg-pubkey packages aren't really pacakges, so we have to do
                # something a little different.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__gpg_req__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                      % (entry.tag, entry.get('name')))
                    return False
            elif entry.tag == 'Path' and entry.get('type') == 'ignore':
                # ignored Paths are only relevant during failed package
                # verification
                pass
            else:
                if [attr for attr in self.__req__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                      % (entry.tag, entry.get('name')))
                    return False
        else:
            if entry.get('name') == 'gpg-pubkey':
                # gpg-pubkey packages aren't really pacakges, so we have to do
                # something a little different.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__new_gpg_req__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                      % (entry.tag, entry.get('name')))
                    return False
                # Check that the Instance Level has what we need for verification.
                for inst in instances:
                    if [attr for attr in self.__new_gpg_req__[inst.tag] \
                                 if attr not in inst.attrib]:
                        self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                          % (inst.tag, inst.get('name')))
                        return False
            else:
                # New format with Instances, or old style modified.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__new_req__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                      % (entry.tag, entry.get('name')))
                    return False
                # Check that the Instance Level has what we need for verification.
                for inst in instances:
                    if inst.tag == 'Instance':
                        if [attr for attr in self.__new_req__[inst.tag] \
                                     if attr not in inst.attrib]:
                            self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                              % (inst.tag, inst.get('name')))
                            return False
        return True

    def FindExtra(self):
        """Find extra packages."""
        packages = [entry.get('name') for entry in self.getSupportedEntries()]
        extras = []

        for (name, instances) in list(self.installed.items()):
            if name not in packages:
                extra_entry = Bcfg2.Client.XML.Element('Package', name=name, type=self.pkgtype)
                for installed_inst in instances:
                    if self.setup['extra']:
                        self.logger.info("Extra Package %s %s." % \
                                         (name, self.str_evra(installed_inst)))
                    tmp_entry = Bcfg2.Client.XML.SubElement(extra_entry, 'Instance', \
                                     version = installed_inst.get('version'), \
                                     release = installed_inst.get('release'))
                    if installed_inst.get('epoch', None) != None:
                        tmp_entry.set('epoch', str(installed_inst.get('epoch')))
                    if installed_inst.get('arch', None) != None:
                        tmp_entry.set('arch', installed_inst.get('arch'))
                extras.append(extra_entry)
        return extras


    def FindExtraInstances(self, pkg_entry, installed_entry):
        """
            Check for installed instances that are not in the config.
            Return a Package Entry with Instances to remove, or None if there
            are no Instances to remove.

        """
        name = pkg_entry.get('name')
        extra_entry = Bcfg2.Client.XML.Element('Package', name=name, type=self.pkgtype)
        instances = [inst for inst in pkg_entry if inst.tag == 'Instance' or inst.tag == 'Package']
        if name in self.installOnlyPkgs:
            for installed_inst in installed_entry:
                not_found = True
                for inst in instances:
                    if self.pkg_vr_equal(inst, installed_inst) or \
                       self.inst_evra_equal(inst, installed_inst):
                        not_found = False
                        break
                if not_found == True:
                    # Extra package.
                    self.logger.info("Extra InstallOnlyPackage %s %s." % \
                                     (name, self.str_evra(installed_inst)))
                    tmp_entry = Bcfg2.Client.XML.SubElement(extra_entry, 'Instance', \
                                     version = installed_inst.get('version'), \
                                     release = installed_inst.get('release'))
                    if installed_inst.get('epoch', None) != None:
                        tmp_entry.set('epoch', str(installed_inst.get('epoch')))
                    if installed_inst.get('arch', None) != None:
                        tmp_entry.set('arch', installed_inst.get('arch'))
        else:
            # Normal package, only check arch.
            for installed_inst in installed_entry:
                not_found = True
                for inst in instances:
                    if installed_inst.get('arch', None) == inst.get('arch', None) or\
                       inst.tag == 'Package':
                        not_found = False
                        break
                if not_found:
                    self.logger.info("Extra Normal Package Instance %s %s" % \
                                     (name, self.str_evra(installed_inst)))
                    tmp_entry = Bcfg2.Client.XML.SubElement(extra_entry, 'Instance', \
                                     version = installed_inst.get('version'), \
                                     release = installed_inst.get('release'))
                    if installed_inst.get('epoch', None) != None:
                        tmp_entry.set('epoch', str(installed_inst.get('epoch')))
                    if installed_inst.get('arch', None) != None:
                        tmp_entry.set('arch', installed_inst.get('arch'))

        if len(extra_entry) == 0:
            extra_entry = None

        return extra_entry

    def str_evra(self, instance):
        """Convert evra dict entries to a string."""
        if instance.get('epoch', '*') in ['*', None]:
            return '%s-%s.%s' % (instance.get('version', '*'),
                                 instance.get('release', '*'),
                                 instance.get('arch', '*'))
        else:
            return '%s:%s-%s.%s' % (instance.get('epoch', '*'),
                                    instance.get('version', '*'),
                                    instance.get('release', '*'),
                                    instance.get('arch', '*'))

    def pkg_vr_equal(self, config_entry, installed_entry):
        '''
            Compare old style entry to installed entry.  Which means ignore
            the epoch and arch.
        '''
        if (config_entry.tag == 'Package' and \
            config_entry.get('version') == installed_entry.get('version') and \
            config_entry.get('release') == installed_entry.get('release')):
            return True
        else:
            return False

    def inst_evra_equal(self, config_entry, installed_entry):
        """Compare new style instance to installed entry."""

        if config_entry.get('epoch', None) != None:
            epoch = int(config_entry.get('epoch'))
        else:
            epoch = None

        if (config_entry.tag == 'Instance' and \
           (epoch == installed_entry.get('epoch', 0) or \
               (epoch == 0 and installed_entry.get('epoch', 0) == None) or \
               (epoch == None and installed_entry.get('epoch', 0) == 0)) and \
           config_entry.get('version') == installed_entry.get('version') and \
           config_entry.get('release') == installed_entry.get('release') and \
           config_entry.get('arch', None) == installed_entry.get('arch', None)):
            return True
        else:
            return False

    def getinstalledgpg(self):
        """
           Create a list of installed GPG key IDs.

           The pgp-pubkey package version is the least significant 4 bytes
           (big-endian) of the key ID which is good enough for our purposes.

        """
        init_ts = rpmtools.rpmtransactionset()
        init_ts.setVSFlags(rpm._RPMVSF_NODIGESTS|rpm._RPMVSF_NOSIGNATURES)
        gpg_hdrs = rpmtools.getheadersbykeyword(init_ts, **{'name':'gpg-pubkey'})
        keyids = [ header[rpm.RPMTAG_VERSION] for header in gpg_hdrs]
        keyids.append('None')
        init_ts.closeDB()
        del init_ts
        return keyids

    def VerifyPath(self, entry, _):
        """
           We don't do anything here since all
           Paths are processed in __init__
        """
        return True
