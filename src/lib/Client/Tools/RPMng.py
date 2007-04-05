'''Bcfg2 Support for RPMS'''

__revision__ = '$Revision$'

import Bcfg2.Client.Tools, time, rpmtools, sys

class RPMng(Bcfg2.Client.Tools.PkgTool):
    '''Support for RPM packages'''
    __name__ = 'RPMng'
    __execs__ = ['/bin/rpm', '/var/lib/rpm']
    __handles__ = [('Package', 'rpm')]

    __req__ = {'Package': ['name', 'version']}
    __ireq__ = {'Package': ['name', 'version', 'url']}
    
    __new_req__ = {'Package': ['name'], 'Instance': ['version', 'release', 'arch']}
    __new_ireq__ = {'Package': ['name', 'uri'], \
                    'Instance': ['simplefile', 'version', 'release', 'arch']}
    
    __gpg_req__ = {'Package': ['name'], 'Instance': ['version', 'release']}
    __gpg_ireq__ = {'Package': ['name'], 'Instance': ['version', 'release']}

    conflicts = ['RPM']

    pkgtype = 'rpm'
    pkgtool = ("rpm --oldpackage --replacepkgs --quiet -U %s", ("%s", ["url"]))

    # This is mostly the default list from YUM on Centos 4.  Check these are 
    # still correct.
    # ***** Should probably put in bcfg2.config somewhere. *****
    installOnlyPkgs = ['kernel', 'kernel-bigmem', 'kernel-enterprise', 'kernel-smp',
                       'kernel-modules', 'kernel-debug', 'kernel-unsupported',
                       'kernel-source', 'kernel-devel', 'kernel-default',
                       'kernel-largesmp-devel', 'kernel-largesmp', 'gpg-pubkey']
    
    def __init__(self, logger, setup, config, states):
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, setup, config, states)

        self.instance_status = {}

    def RefreshPackages(self):
        '''
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
        '''
        self.installed = {}
        refresh_ts = rpmtools.rpmtransactionset()
        for nevra in rpmtools.rpmpackagelist(refresh_ts):
            self.installed.setdefault(nevra['name'], []).append(nevra)
        if self.setup['debug']:
            print "The following package instances are installed:"
            for name, instances in self.installed.iteritems():
                self.logger.info("    " + name)
                for inst in instances:
                    self.logger.info("        %s:%s-%s.%s" % \
                                         (inst.get('epoch', None), inst.get('version', None), 
                                          inst.get('release', None), inst.get('arch', None)))
        refresh_ts.closeDB()

    def VerifyPackage(self, entry, modlist):
        '''
            Verify Package status for entry.
            Compares the 'version' info against self.installed{} and does 
            an rpm level package verify.

            Code for the old/new style Package Entries has been kept separate,
            even though it has meant some code duplication, so that the old style 
            code can be easily removed at a later date.
        '''

        instances = entry.findall('Instance')
        if not instances:
            # We have an old style no Instance entry.
            if entry.get('release', None) == None:
                version, release = entry.get('version').split('-')
                entry.set('version', version)
                entry.set('release', release)
            instances = [ entry ]

        vp_ts = rpmtools.rpmtransactionset()

        self.logger.info("Verifying package instances for %s" % entry.get('name'))
        package_fail = False
        qtext_versions = ''

        if self.installed.has_key(entry.get('name')):
            # There is at least one instance installed.
            if entry.get('name') in self.installOnlyPkgs:
                # Packages that should only be installed or removed.
                # e.g. kernels.
                self.logger.info("        Install only package.")
                for inst in instances:
                    self.instance_status.setdefault(inst, {})['installed'] = False
                    self.instance_status[inst]['version_fail'] = False
                    if inst.tag == 'Package' and len(self.installed[entry.get('name')]) > 1:
                        self.logger.error("WARNING: Multiple instances of package %s are installed." % (entry.get('name')))
                    for pkg in self.installed[entry.get('name')]:
                        if inst.tag == 'Package':
                            # We have an old style Package entry that does not
                            # have an epoch or an arch, so scrub them from 
                            # installed{}.
                            pkg.pop('arch', None)
                            pkg.pop('epoch', None)
                        if inst.get('epoch', None) != None:
                            epoch = int(inst.get('epoch'))
                        else:
                            epoch = None
                        if epoch == pkg.get('epoch') and \
                           inst.get('version') == pkg.get('version') and \
                           inst.get('release') == pkg.get('release') and \
                           inst.get('arch', None) == pkg.get('arch', None):
                            self.logger.info("        %s:%s-%s.%s" % \
                                     (inst.get('epoch', None), inst.get('version'), 
                                      inst.get('release'), inst.get('arch', None)))
                            self.logger.debug("        verify_flags = %s" % \
                                                           (inst.get('verify_flags', [])))
                            self.instance_status[inst]['installed'] = True
                            self.instance_status[inst]['verify'] = \
                                  rpmtools.rpm_verify( vp_ts, pkg, \
                                                       inst.get('verify_flags', '').split(','))

                    if self.instance_status[inst]['installed'] == False:
                        package_fail = True
                        self.logger.info("        Package %s %s:%s-%s.%s not installed." % \
                                     (entry.get('name'),
                                      inst.get('epoch', None), inst.get('version'), 
                                      inst.get('release'), inst.get('arch', None)))
                            
                        qtext_versions = qtext_versions + '%s:%s-%s.%s ' % \
                                            (inst.get('epoch', ''), inst.get('version', ''),\
                                             inst.get('release', ''), inst.get('arch', ''))
                  
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
                            if inst.tag == 'Package':
                                # We have an old style Package entry that does not
                                # have an epoch or an arch, so scrub them from 
                                # installed{}.
                                pkg.pop('arch', None)
                                pkg.pop('epoch', None)
                            if inst.get('epoch', None) != None:
                                epoch = int(inst.get('epoch'))
                            else:
                                epoch = None
                            if epoch == pkg.get('epoch', None) and \
                               inst.get('version') == pkg.get('version') and \
                               inst.get('release') == pkg.get('release'):
                                self.logger.info("        %s:%s-%s.%s" % \
                                            (inst.get('epoch', None), inst.get('version', ''), \
                                             inst.get('release', ''), inst.get('arch', None)))
                                self.logger.debug("        verify_flags = %s" % \
                                                              (inst.get('verify_flags', [])))
                                self.instance_status[inst]['installed'] = True
                                self.instance_status[inst]['verify'] = \
                                   rpmtools.rpm_verify( vp_ts, pkg,\
                                                        inst.get('verify_flags', '').split(','))
                            else:
                                package_fail = True
                                self.instance_status[inst]['version_fail'] = True
                                self.logger.info("        Wrong version installed.  Want %s:%s-%s.%s, but have %s:%s-%s.%s" % \
                                            (inst.get('epoch', None), inst.get('version'), \
                                             inst.get('release'), inst.get('arch', None), \
                                             pkg.get('epoch'), pkg.get('version'), \
                                             pkg.get('release'), pkg.get('arch')))
                        
                                qtext_versions = qtext_versions + \
                                            '(%s:%s-%s.%s -> %s:%s-%s.%s) ' % \
                                            (pkg.get('epoch', ''), pkg.get('version'), \
                                             pkg.get('release'), pkg.get('arch', ''), \
                                             inst.get('epoch', ''), inst.get('version'), \
                                             inst.get('release'), inst.get('arch', ''))
                    elif len(arch_match) == 0:
                        # This instance is not installed.
                        self.instance_status[inst]['installed'] = False
                        
                        self.logger.info("        %s:%s-%s.%s is not installed." % \
                                            (inst.get('epoch', None), inst.get('version'), \
                                             inst.get('release'), inst.get('arch', None)))
                        
                        qtext_versions = qtext_versions + '%s:%s-%s.%s ' % \
                                            (inst.get('epoch', ''), inst.get('version'), \
                                             inst.get('release'), inst.get('arch', ''))
                  
                        entry.set('current_exists', 'false')

            for inst in instances:
                instance_fail = False
                # Dump the rpm verify results. 
                #****Write something to format this nicely.*****
                if self.setup['debug'] and self.instance_status[inst].get('verify', None):
                    self.logger.debug(self.instance_status[inst]['verify'])

                # Check the rpm verify results.
                if self.instance_status[inst].get('verify', None):
                    if len(self.instance_status[inst].get('verify')) > 1:
                        self.logger.info("WARNING: Verification of more than one package instance.")
                 
                    self.instance_status[inst]['verify_fail'] = False

                    for result in self.instance_status[inst]['verify']:

                        # Check header results
                        if result.get('hdr', []):
                            package_fail = True
                            instance_fail = True
                            self.instance_status[inst]['verify_fail'] = True
    
                        # Check dependency results
                        if result.get('deps', []):
                            package_fail = True
                            instance_fail = True
                            self.instance_status[inst]['verify_fail'] = True
                         
                        # Check the rpm verify file results against the modlist
                        # and per Instance Ignores.
                        for file_result in result.get('files', []):
                            if file_result[-1] not in modlist and \
                               file_result[-1] not in \
                                          [ignore.get('name') for ignore in inst.findall('Ignore')]:
                                package_fail = True
                                instance_fail = True
                                self.instance_status[inst]['verify_fail'] = True
                            else:
                                self.logger.info("        Modlist/Ignore match: %s" % \
                                                                               (file_result[-1]))

                    if instance_fail == True:
                        self.logger.info("*** Instance %s:%s-%s.%s failed RPM verification ***" % \
                                           (inst.get('epoch', None), inst.get('version'), \
                                            inst.get('release'), inst.get('arch', None)))
                        
                        qtext_versions = qtext_versions + '%s:%s-%s.%s ' % \
                                            (inst.get('epoch', ''), inst.get('version'), \
                                             inst.get('release'), inst.get('arch', ''))

                if self.instance_status[inst]['installed'] == False or \
                   self.instance_status[inst]['version_fail'] == True:
                    package_fail = True

            if package_fail == True:
                self.logger.info("        Package %s failed verification." % \
                                                                        (entry.get('name')))
                qtext = 'Upgrade/downgrade Package %s instance(s) - %s (y/N) ' % \
                                              (entry.get('name'), qtext_versions)
                entry.set('qtext', qtext)
                entry.set('current_version', "%s:%s-%s.%s" % \
                                (inst.get('epoch', None), inst.get('version'), 
                                 inst.get('release'), inst.get('arch', None)))
                return False

        else:
            # There are no Instances of this package installed.
            self.logger.debug("Package %s has no instances installed" % (entry.get('name')))
            entry.set('current_exists', 'false')
            for inst in instances:
                qtext_versions = qtext_versions + '%s:%s-%s.%s ' % \
                                (inst.get('epoch', None), inst.get('version'),
                                 inst.get('release'), inst.get('arch', None))
                self.instance_status.setdefault(inst, {})['installed'] = False

            entry.set('qtext', "Install Package %s Instance(s) %s? (y/N) " % \
                                                        (entry.get('name'), qtext_versions))
                          
            return False
        return True

    def RemovePackages(self, packages):
        '''Remove specified entries'''
        #pkgnames = [pkg.get('name') for pkg in packages]
        #if len(pkgnames) > 0:
        #    self.logger.info("Removing packages: %s" % pkgnames)
        #    if self.cmd.run("rpm --quiet -e --allmatches %s" % " ".join(pkgnames))[0] == 0:
        #        self.modified += packages
        #    else:
        #        for pkg in packages:
        #            if self.cmd.run("rpm --quiet -e --allmatches %s" % \
        #                            pkg.get('name'))[0] == 0:
        #                self.modified += pkg
        #
        # self.RefreshPackages()
        #    self.extra = self.FindExtraPackages()
        print "The following package instances would have been deleted:"
        for pkg in packages:
            print "    %s:" % (pkg.get('name'))
            for inst in pkg:
                print "        %s:%s-%s.%s" % (inst.get('epoch', None), inst.get('version'), \
                                               inst.get('release'), inst.get('arch', None))

    def Install(self, packages):
        '''
        '''
        self.logger.info('''The following packages have something wrong with them and RPM.Install()
                 will try and do something to fix them if appropriate:''')

        for pkg in packages:
            instances = pkg.findall('Instance')
            if not instances:
                instances = [ pkg ]
            for inst in instances:
                if self.instance_status[inst].get('installed', False) == False or \
                   self.instance_status[inst].get('version_fail', False) == True or \
                   self.instance_status[inst].get('verify_fail', False) == True:
                    print "%s: %s:%s-%s.%s installed = %s, Version_fail = %s, verify_fail = %s" % \
                        (pkg.get('name'),inst.get('epoch', None), inst.get('version'), \
                         inst.get('release'), inst.get('arch', None), \
                         self.instance_status[inst].get('installed', None),\
                         self.instance_status[inst].get('version_fail', None),\
                         self.instance_status[inst].get('verify_fail', None))

    def canInstall(self, entry):
        '''
            test if entry has enough information to be installed
        '''
        if not self.handlesEntry(entry):
            return False

        instances = entry.findall('Instance')

        if not instances:
            # Old non Instance format.
            if [attr for attr in self.__ireq__[entry.tag] if attr not in entry.attrib]:
                self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                  % (entry.tag, entry.get('name')))
                return False
        else:
            if entry.get('name') == 'gpg-pubkey':
                # gpg-pubkey packages aren't really pacakges, so we have to do
                # something a little different.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__gpg_ireq__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                      % (entry.tag, entry.get('name')))
                    return False
                # Check that the Instance Level has what we need for verification.
                for inst in instances:
                    if [attr for attr in self.__gpg_ireq__[inst.tag] if attr not in inst.attrib]:
                        self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                          % (inst.tag, inst.get('name')))
                        return False
            else:
                # New format with Instances.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__new_ireq__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                      % (entry.tag, entry.get('name')))
                    return False
                # Check that the Instance Level has what we need for verification.
                for inst in instances:
                    if [attr for attr in self.__new_ireq__[inst.tag] if attr not in inst.attrib]:
                        self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                          % (inst.tag, inst.get('name')))
                        return False
        return True

    def canVerify(self, entry):
        '''
            Test if entry has enough information to be verified.
 
            Three types of entries are checked.
               Old style Package
               New style Package with Instances
               pgp-pubkey packages
        '''
        if not self.handlesEntry(entry):
            return False

        instances = entry.findall('Instance')

        if not instances:
            # Old non Instance format.
            if [attr for attr in self.__req__[entry.tag] if attr not in entry.attrib]:
                self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                  % (entry.tag, entry.get('name')))
                return False
        else:
            if entry.get('name') == 'gpg-pubkey':
                # gpg-pubkey packages aren't really pacakges, so we have to do 
                # something a little different.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__gpg_req__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                      % (entry.tag, entry.get('name')))
                    return False
                # Check that the Instance Level has what we need for verification.
                for inst in instances:
                    if [attr for attr in self.__gpg_req__[inst.tag] if attr not in inst.attrib]:
                        self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                          % (inst.tag, inst.get('name')))
                        return False
            else:
                # New format with Instances.
                # Check that the Package Level has what we need for verification.
                if [attr for attr in self.__new_req__[entry.tag] if attr not in entry.attrib]:
                    self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                      % (entry.tag, entry.get('name')))
                    return False
                # Check that the Instance Level has what we need for verification.
                for inst in instances:
                    if [attr for attr in self.__new_req__[inst.tag] if attr not in inst.attrib]:
                        self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                                          % (inst.tag, inst.get('name')))
                        return False
        return True

    def FindExtraPackages(self):
        '''
           Find extra packages
        '''
        extra_packages = []
        packages = {}
        for entry in self.getSupportedEntries():
            packages[entry.get('name')] = entry

        for name, pkg_list in self.installed.iteritems():
            extra_entry = Bcfg2.Client.XML.Element('Package', name=name, type=self.pkgtype)
            if packages.get(name, None) != None:
                # There is supposed to be at least one instance installed.
                instances = packages[name].findall('Instance')
                if not instances:
                    instances = [ packages[name] ]
                if name in self.installOnlyPkgs:
                    for installed_inst in pkg_list:
                        not_found = True
                        for inst in instances:
                            if inst.get('epoch', None) != None:
                                epoch = int(inst.get('epoch'))
                            else:
                                epoch = None
                            if epoch == installed_inst.get('epoch') and \
                               inst.get('version') == installed_inst.get('version') and \
                               inst.get('release') == installed_inst.get('release') and \
                               inst.get('arch', None) == installed_inst.get('arch'):
                                not_found = False
                                break
                        if not_found == True:
                            # Extra package.
                            self.logger.info("Extra InstallOnlyPackage %s %s:%s-%s.%s." % \
                                 (name, installed_inst.get('epoch'), \
                                        installed_inst.get('version'), \
                                        installed_inst.get('release'), \
                                        installed_inst.get('arch')))
                            if inst.tag == 'Package':
                                Bcfg2.Client.XML.SubElement(extra_entry, \
                                             'Instance', 
                                             version = installed_inst.get('version'), \
                                             release = installed_inst.get('release'))
                            else:
                                Bcfg2.Client.XML.SubElement(extra_entry, \
                                             'Instance', 
                                             epoch = str(installed_inst.get('epoch')),\
                                             version = installed_inst.get('version'), \
                                             release = installed_inst.get('release'), \
                                             arch = installed_inst.get('arch', ''))
                else:
                    # Normal package, only check arch.
                    for installed_inst in pkg_list:
                        not_found = True
                        for inst in instances:
                            if installed_inst.get('arch') == inst.get('arch'):
                                not_found = False
                                break
                        if not_found:
                            self.logger.info("Extra Normal Package Instance %s %s:%s-%s.%s." % \
                                 (name, installed_inst.get('epoch'), \
                                        installed_inst.get('version'), \
                                        installed_inst.get('release'), \
                                        installed_inst.get('arch')))
                            if inst.tag == 'Package':
                                Bcfg2.Client.XML.SubElement(extra_entry, \
                                             'Instance', 
                                             version = installed_inst.get('version'), \
                                             release = installed_inst.get('release'))
                            else:
                                Bcfg2.Client.XML.SubElement(extra_entry, \
                                             'Instance', 
                                             epoch = str(installed_inst.get('epoch')),\
                                             version = installed_inst.get('version'), \
                                             release = installed_inst.get('release'), \
                                             arch = installed_inst.get('arch', ''))
            else:
                # Extra package.
                self.logger.info("No instances of Package %s should be installed." % (name))
                for installed_inst in pkg_list:
                    if inst.tag == 'Package':
                        Bcfg2.Client.XML.SubElement(extra_entry, \
                                     'Instance', 
                                     version = installed_inst.get('version'), \
                                     release = installed_inst.get('release'))
                    else:
                        Bcfg2.Client.XML.SubElement(extra_entry, \
                                     'Instance', 
                                     epoch = str(installed_inst.get('epoch')),\
                                     version = installed_inst.get('version'), \
                                     release = installed_inst.get('release'), \
                                     arch = installed_inst.get('arch', ''))
            if len(extra_entry) > 0:
                extra_packages.append(extra_entry)
            else:
                del extra_entry
        return extra_packages


 
