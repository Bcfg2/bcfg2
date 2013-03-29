"""This provides bcfg2 support for yum."""

import copy
import os.path
import sys
import yum
import yum.packages
import yum.rpmtrans
import yum.callbacks
import yum.Errors
import yum.misc
import rpmUtils.arch
import Bcfg2.Client.XML
import Bcfg2.Client.Tools


def build_yname(pkgname, inst):
    """Build yum appropriate package name."""
    rv = {}
    if isinstance(inst, yum.packages.PackageObject):
        for i in ['name', 'epoch', 'version', 'release', 'arch']:
            rv[i] = getattr(inst, i)
    else:
        rv['name'] = pkgname
        if inst.get('version') != 'any':
            rv['version'] = inst.get('version')
        if inst.get('epoch', False):
            rv['epoch'] = inst.get('epoch')
        if inst.get('release', False) and inst.get('release') != 'any':
            rv['release'] = inst.get('release')
        if inst.get('arch', False) and inst.get('arch') != 'any':
            rv['arch'] = inst.get('arch')
    return rv


def short_yname(nevra):
    """ given a nevra dict, get a dict of options to pass to functions
    like yum.YumBase.rpmdb.searchNevra(), which expect short names
    (e.g., "rel" instead of "release") """
    rv = nevra.copy()
    if 'version' in rv:
        rv['ver'] = rv['version']
        del rv['version']
    if 'release' in rv:
        rv['rel'] = rv['release']
        del rv['release']
    return rv


def nevra2string(pkg):
    """ convert a yum package object or nevra dict to a friendly
    human-readable string """
    if isinstance(pkg, yum.packages.PackageObject):
        return str(pkg)
    else:
        ret = []
        for attr, fmt in [('epoch', '%s:'), ('name', '%s'), ('version', '-%s'),
                          ('release', '-%s'), ('arch', '.%s')]:
            if attr in pkg:
                ret.append(fmt % pkg[attr])
        return "".join(ret)


class RPMDisplay(yum.rpmtrans.RPMBaseCallback):
    """We subclass the default RPM transaction callback so that we
       can control Yum's verbosity and pipe it through the right logger."""

    def __init__(self, logger):
        yum.rpmtrans.RPMBaseCallback.__init__(self)
        # we want to log events to *both* the Bcfg2 logger (which goes
        # to stderr or syslog or wherever the user wants it to go)
        # *and* the yum file logger, which will go to yum.log (ticket
        # #1103)
        self.bcfg2_logger = logger
        self.state = None
        self.package = None

    def event(self, package, action, te_current, te_total,
              ts_current, ts_total):
        """
        @param package: A yum package object or simple string of a package name
        @param action: A yum.constant transaction set state or in the obscure
                       rpm repackage case it could be the string 'repackaging'
        @param te_current: Current number of bytes processed in the transaction
                           element being processed
        @param te_total: Total number of bytes in the transaction element being
                         processed
        @param ts_current: number of processes completed in whole transaction
        @param ts_total: total number of processes in the transaction.
        """

        if self.package != str(package) or action != self.state:
            self.bcfg2_logger.info("%s: %s" % (self.action[action], package))
            self.state = action
            self.package = str(package)

    def scriptout(self, package, msgs):
        """Handle output from package scripts."""

        if msgs:
            msg = "%s: %s" % (package, msgs)
            self.bcfg2_logger.debug(msg)

    def errorlog(self, msg):
        """Deal with error reporting."""
        self.bcfg2_logger.error(msg)


class YumDisplay(yum.callbacks.ProcessTransBaseCallback):
    """Class to handle display of what step we are in the Yum transaction
       such as downloading packages, etc."""

    def __init__(self, logger):
        yum.callbacks.ProcessTransBaseCallback.__init__(self)
        self.logger = logger


class YUM(Bcfg2.Client.Tools.PkgTool):
    """Support for Yum packages."""
    pkgtype = 'yum'
    __execs__ = []
    __handles__ = [('Package', 'yum'),
                   ('Package', 'rpm'),
                   ('Path', 'ignore')]

    __req__ = {'Package': ['type'],
               'Path': ['type']}

    conflicts = ['YUM24', 'RPM', 'RPMng', 'YUMng']

    def __init__(self, logger, setup, config):
        self.yumbase = self._loadYumBase(setup=setup, logger=logger)
        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, setup, config)
        self.ignores = []
        for struct in config:
            self.ignores.extend([entry.get('name')
                                 for entry in struct
                                 if (entry.tag == 'Path' and
                                     entry.get('type') == 'ignore')])
        self.instance_status = {}
        self.extra_instances = []
        self.modlists = {}
        for struct in config:
            self.__important__.extend(
                [entry.get('name')
                 for entry in struct
                 if (entry.tag == 'Path' and
                     (entry.get('name').startswith('/etc/yum.d') or
                      entry.get('name').startswith('/etc/yum.repos.d')) or
                     entry.get('name') == '/etc/yum.conf')])
        self.yum_avail = dict()
        self.yum_installed = dict()
        self.verify_cache = dict()

        yup = self.yumbase.doPackageLists(pkgnarrow='updates')
        if hasattr(self.yumbase.rpmdb, 'pkglist'):
            yinst = self.yumbase.rpmdb.pkglist
        else:
            yinst = self.yumbase.rpmdb.getPkgList()
        for dest, source in [(self.yum_avail, yup.updates),
                             (self.yum_installed, yinst)]:
            for pkg in source:
                if dest is self.yum_avail:
                    pname = pkg.name
                    data = [(pkg.arch, (pkg.epoch, pkg.version, pkg.release))]
                else:
                    pname = pkg[0]
                    data = [(pkg[1], (pkg[2], pkg[3], pkg[4]))]
                if pname in dest:
                    dest[pname].update(data)
                else:
                    dest[pname] = dict(data)

        # Process the Yum section from the config file.  These are all
        # boolean flags, either we do stuff or we don't
        self.pkg_checks = self.setup["yum_pkg_checks"]
        self.pkg_verify = self.setup["yum_pkg_verify"]
        self.do_install = self.setup["yum_installed_action"] == "install"
        self.do_upgrade = self.setup["yum_version_fail_action"] == "upgrade"
        self.do_reinst = self.setup["yum_verify_fail_action"] == "reinstall"
        self.verify_flags = self.setup["yum_verify_flags"]

        self.installonlypkgs = self.yumbase.conf.installonlypkgs
        if 'gpg-pubkey' not in self.installonlypkgs:
            self.installonlypkgs.append('gpg-pubkey')

        self.logger.debug("Yum: Install missing: %s" % self.do_install)
        self.logger.debug("Yum: pkg_checks: %s" % self.pkg_checks)
        self.logger.debug("Yum: pkg_verify: %s" % self.pkg_verify)
        self.logger.debug("Yum: Upgrade on version fail: %s" % self.do_upgrade)
        self.logger.debug("Yum: Reinstall on verify fail: %s" % self.do_reinst)
        self.logger.debug("Yum: installonlypkgs: %s" % self.installonlypkgs)
        self.logger.debug("Yum: verify_flags: %s" % self.verify_flags)

    def _loadYumBase(self, setup=None, logger=None):
        ''' this may be called before PkgTool.__init__() is called on
        this object (when the YUM object is first instantiated;
        PkgTool.__init__() calls RefreshPackages(), which requires a
        YumBase object already exist), or after __init__() has
        completed, when we reload the yum config before installing
        packages. Consequently, we support both methods by allowing
        setup and logger, the only object properties we use in this
        function, to be passed as keyword arguments or to be omitted
        and drawn from the object itself.'''
        rv = yum.YumBase()  # pylint: disable=C0103

        if setup is None:
            setup = self.setup
        if logger is None:
            logger = self.logger

        if setup['debug']:
            debuglevel = 3
        elif setup['verbose']:
            debuglevel = 2
        else:
            debuglevel = 0

        # pylint: disable=E1121,W0212
        try:
            rv.preconf.debuglevel = debuglevel
            rv._getConfig()
        except AttributeError:
            rv._getConfig(self.yumbase.conf.config_file_path,
                          debuglevel=debuglevel)
        # pylint: enable=E1121,W0212

        try:
            rv.doConfigSetup()
            rv.doTsSetup()
            rv.doRpmDBSetup()
        except yum.Errors.RepoError:
            logger.error("YUM Repository error: %s" % sys.exc_info()[1])
            raise Bcfg2.Client.Tools.ToolInstantiationError
        except Exception:
            logger.error("Yum error: %s" % sys.exc_info()[1])
            raise Bcfg2.Client.Tools.ToolInstantiationError
        return rv

    def _fixAutoVersion(self, entry):
        """ handle entries with version="auto" by setting the version
        to the newest available """
        # old style entry; synthesize Instances from current installed
        if (entry.get('name') not in self.yum_installed and
            entry.get('name') not in self.yum_avail):
            # new entry; fall back to default
            entry.set('version', 'any')
        else:
            data = copy.copy(self.yum_installed[entry.get('name')])
            if entry.get('name') in self.yum_avail:
                # installed but out of date
                data.update(self.yum_avail[entry.get('name')])
            for (arch, (epoch, vers, rel)) in list(data.items()):
                inst = Bcfg2.Client.XML.SubElement(entry, "Instance",
                                                   name=entry.get('name'),
                                                   version=vers, arch=arch,
                                                   release=rel, epoch=epoch)
                if 'verify_flags' in entry.attrib:
                    inst.set('verify_flags', entry.get('verify_flags'))
                if 'verify' in entry.attrib:
                    inst.set('verify', entry.get('verify'))

    def _buildInstances(self, entry):
        """ get a list of all instances of the package from the given
        entry.  converts from a Package entry without any Instance
        tags as necessary """
        instances = [inst for inst in entry
                     if inst.tag == 'Instance' or inst.tag == 'Package']

        # Uniquify instances.  Cases where duplicates are returned.
        # However, the elements aren't comparable.

        if instances == []:
            # We have an old style no Instance entry. Convert it to new style.
            instance = Bcfg2.Client.XML.SubElement(entry, 'Package')
            for attrib in list(entry.attrib.keys()):
                instance.attrib[attrib] = entry.attrib[attrib]
            instances = [instance]

        return instances

    def _getGPGKeysAsPackages(self):
        """Return a list of the GPG RPM signing keys installed on the
           system as a list of Package Objects."""

        # GPG keys existing in the RPMDB have numbered days
        # and newer Yum versions will not return information about them
        if hasattr(self.yumbase.rpmdb, 'returnGPGPubkeyPackages'):
            return self.yumbase.rpmdb.returnGPGPubkeyPackages()
        return self.yumbase.rpmdb.searchNevra(name='gpg-pubkey')

    def missing_attrs(self, entry):
        """ Implementing from superclass to check for existence of either
        name or group attribute for Package entry in the case of a YUM
        group. """
        missing = Bcfg2.Client.Tools.PkgTool.missing_attrs(self, entry)

        if (entry.get('name', None) is None and
            entry.get('group', None) is None):
            missing += ['name', 'group']
        return missing

    def _verifyHelper(self, pkg_obj):
        """ _verifyHelper primarly deals with a yum bug where the
        pkg_obj.verify() method does not properly take into count multilib
        sharing of files.  Neither does RPM proper, really....it just
        ignores the problem. """
        def verify(pkg):
            """ helper to perform the verify according to the best
            options for whatever version of the API we're
            using. Disabling file checksums is a new feature yum
            3.2.17-ish """
            try:
                return pkg.verify(fast=self.setup.get('quick', False))
            except TypeError:
                # Older Yum API
                return pkg.verify()

        key = (pkg_obj.name, pkg_obj.epoch, pkg_obj.version, pkg_obj.release,
               pkg_obj.arch)
        if key in self.verify_cache:
            results = self.verify_cache[key]
        else:
            results = verify(pkg_obj)
            self.verify_cache[key] = results
        if not rpmUtils.arch.isMultiLibArch():
            return results

        # Okay deal with a buggy yum multilib and verify. first find
        # all arches of pkg
        packages = self.yumbase.rpmdb.searchNevra(name=pkg_obj.name,
                                                  epoch=pkg_obj.epoch,
                                                  ver=pkg_obj.version,
                                                  rel=pkg_obj.release)
        if len(packages) == 1:
            return results  # No mathcing multilib packages

        # Will be the list of common fnames
        files = set(pkg_obj.returnFileEntries())
        common = {}
        for pkg in packages:
            if pkg != pkg_obj:
                files = files & set(pkg.returnFileEntries())
        for pkg in packages:
            key = (pkg.name, pkg.epoch, pkg.version, pkg.release, pkg.arch)
            self.logger.debug("Multilib Verify: comparing %s to %s" %
                              (pkg_obj, pkg))
            if key not in self.verify_cache:
                self.verify_cache[key] = verify(pkg)
            for fname in list(self.verify_cache[key].keys()):
                # file problems must exist in ALL multilib packages to be real
                if fname in files:
                    common[fname] = common.get(fname, 0) + 1

        flag = len(packages) - 1
        for fname, i in list(common.items()):
            if i == flag:
                # this fname had verify problems in all but one of the multilib
                # packages.  That means its correct in the package that's
                # "on top."  Therefore, this is a fake verify problem.
                if fname in results:
                    del results[fname]

        return results

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
        packages = self._getGPGKeysAsPackages() + \
            self.yumbase.rpmdb.returnPackages()
        for pkg in packages:
            pattrs = {}
            for i in ['name', 'epoch', 'version', 'release', 'arch']:
                if i == 'arch' and getattr(pkg, i) is None:
                    pattrs[i] = 'noarch'
                elif i == 'epoch' and getattr(pkg, i) is None:
                    pattrs[i] = '0'
                else:
                    pattrs[i] = getattr(pkg, i)
            self.installed.setdefault(pkg.name, []).append(pattrs)

    # pylint: disable=R0914,R0912,R0915
    def VerifyPackage(self, entry, modlist):
        """ Verify Package status for entry.
        Performs the following:
        * Checks for the presence of required Package Instances.
        * Compares the evra 'version' info against self.installed{}.
        * RPM level package verify (rpm --verify).
        * Checks for the presence of unrequired package instances.

        Produces the following dict and list for Yum.Install() to use:
        * For installs/upgrades/fixes of required instances::
            instance_status = { <Instance Element Object>:
                                       { 'installed': True|False,
                                         'version_fail': True|False,
                                         'verify_fail': True|False,
                                         'pkg': <Package Element Object>,
                                         'modlist': [ <filename>, ... ],
                                         'verify' : [ <rpm --verify results> ]
                                       }, ......
                                  }

        * For deletions of unrequired instances::
            extra_instances = [ <Package Element Object>, ..... ]

        Constructs the text prompts for interactive mode. """
        if entry.get('version', False) == 'auto':
            self._fixAutoVersion(entry)

        if entry.get('group'):
            self.logger.debug("Verifying packages for group %s" %
                              entry.get('group'))
        else:
            self.logger.debug("Verifying package instances for %s" %
                              entry.get('name'))

        self.verify_cache = dict()  # Used for checking multilib packages
        self.modlists[entry] = modlist
        instances = self._buildInstances(entry)
        pkg_cache = []
        package_fail = False
        qtext_versions = []
        virt_pkg = False
        pkg_checks = (self.pkg_checks and
                      entry.get('pkg_checks', 'true').lower() == 'true')
        pkg_verify = (self.pkg_verify and
                      entry.get('pkg_verify', 'true').lower() == 'true')
        yum_group = False

        if entry.get('name') == 'gpg-pubkey':
            all_pkg_objs = self._getGPGKeysAsPackages()
            pkg_verify = False  # No files here to verify
        elif entry.get('group'):
            entry.set('name', 'group:%s' % entry.get('group'))
            yum_group = True
            all_pkg_objs = []
            instances = []
            if self.yumbase.comps.has_group(entry.get('group')):
                group = self.yumbase.comps.return_group(entry.get('group'))
                group_packages = [p
                                  for p, d in group.mandatory_packages.items()
                                  if d]
                group_type = entry.get('choose', 'default')
                if group_type in ['default', 'optional', 'all']:
                    group_packages += [
                        p for p, d in group.default_packages.items()
                        if d]
                if group_type in ['optional', 'all']:
                    group_packages += [
                        p for p, d in group.optional_packages.items()
                        if d]
                if len(group_packages) == 0:
                    self.logger.error("No packages found for group %s" %
                                      entry.get("group"))
                for pkg in group_packages:
                    # create package instances for each package in yum group
                    instance = Bcfg2.Client.XML.SubElement(entry, 'Package')
                    instance.attrib['name'] = pkg
                    instance.attrib['type'] = 'yum'
                    try:
                        newest = \
                            self.yumbase.pkgSack.returnNewestByName(pkg)[0]
                        instance.attrib['version'] = newest['version']
                        instance.attrib['epoch'] = newest['epoch']
                        instance.attrib['release'] = newest['release']
                    except:  # pylint: disable=W0702
                        self.logger.info("Error finding newest package "
                                         "for %s" %
                                         pkg)
                        instance.attrib['version'] = 'any'
                    instances.append(instance)
            else:
                self.logger.error("Group not found: %s" % entry.get("group"))
        else:
            all_pkg_objs = \
                self.yumbase.rpmdb.searchNevra(name=entry.get('name'))
        if len(all_pkg_objs) == 0 and yum_group is not True:
            # Some sort of virtual capability?  Try to resolve it
            all_pkg_objs = self.yumbase.rpmdb.searchProvides(entry.get('name'))
            if len(all_pkg_objs) > 0:
                virt_pkg = True
                self.logger.info("%s appears to be provided by:" %
                                 entry.get('name'))
                for pkg in all_pkg_objs:
                    self.logger.info("  %s" % pkg)

        for inst in instances:
            if yum_group:
                # the entry is not the name of the package
                nevra = build_yname(inst.get('name'), inst)
                all_pkg_objs = \
                    self.yumbase.rpmdb.searchNevra(name=inst.get('name'))
            else:
                nevra = build_yname(entry.get('name'), inst)
            if nevra in pkg_cache:
                continue  # Ignore duplicate instances
            else:
                pkg_cache.append(nevra)

            self.logger.debug("Verifying: %s" % nevra2string(nevra))

            # Set some defaults here
            stat = self.instance_status.setdefault(inst, {})
            stat['installed'] = True
            stat['version_fail'] = False
            stat['verify'] = {}
            stat['verify_fail'] = False
            if yum_group:
                stat['pkg'] = inst
            else:
                stat['pkg'] = entry
            stat['modlist'] = modlist
            if inst.get('verify_flags'):
                # this splits on either space or comma
                verify_flags = \
                    inst.get('verify_flags').lower().replace(' ',
                                                             ',').split(',')
            else:
                verify_flags = self.verify_flags

            if 'arch' in nevra:
                # If arch is specified use it to select the package
                pkg_objs = [p for p in all_pkg_objs if p.arch == nevra['arch']]
            else:
                pkg_objs = all_pkg_objs
            if len(pkg_objs) == 0:
                # Package (name, arch) not installed
                entry.set('current_exists', 'false')
                self.logger.debug("  %s is not installed" %
                                  nevra2string(nevra))
                stat['installed'] = False
                package_fail = True
                qtext_versions.append("I(%s)" % nevra)
                continue

            if not pkg_checks:
                continue

            # Check EVR
            if virt_pkg:
                # we need to make sure that the version of the symbol
                # provided matches the one required in the
                # configuration
                vlist = []
                for attr in ["epoch", "version", "release"]:
                    vlist.append(nevra.get(attr))
                if tuple(vlist) == (None, None, None):
                    # we just require the package name, no particular
                    # version, so just make a copy of all_pkg_objs since every
                    # package that provides this symbol satisfies the
                    # requirement
                    pkg_objs = [po for po in all_pkg_objs]
                else:
                    pkg_objs = [po for po in all_pkg_objs
                                if po.checkPrco('provides',
                                                (nevra["name"], 'EQ',
                                                 tuple(vlist)))]
            elif entry.get('name') == 'gpg-pubkey':
                if 'version' not in nevra:
                    self.logger.warning("Skipping verify: gpg-pubkey without "
                                        "an RPM version")
                    continue
                if 'release' not in nevra:
                    self.logger.warning("Skipping verify: gpg-pubkey without "
                                        "an RPM release")
                    continue
                pkg_objs = [p for p in all_pkg_objs
                            if (p.version == nevra['version']
                                and p.release == nevra['release'])]
            else:
                pkg_objs = self.yumbase.rpmdb.searchNevra(**short_yname(nevra))
            if len(pkg_objs) == 0:
                package_fail = True
                stat['version_fail'] = True
                # Just chose the first pkg for the error message
                if virt_pkg:
                    provides = \
                        [p for p in all_pkg_objs[0].provides
                         if p[0] == entry.get("name")][0]
                    entry.set('current_version', "%s:%s-%s" % provides[2])
                    self.logger.info(
                        "  %s: Wrong version installed.  "
                        "Want %s, but %s provides %s" %
                        (entry.get("name"),
                         nevra2string(nevra),
                         nevra2string(all_pkg_objs[0]),
                         yum.misc.prco_tuple_to_string(provides)))
                else:
                    entry.set('current_version', "%s:%s-%s.%s" %
                              (all_pkg_objs[0].epoch,
                               all_pkg_objs[0].version,
                               all_pkg_objs[0].release,
                               all_pkg_objs[0].arch))
                    self.logger.info("  %s: Wrong version installed.  "
                                     "Want %s, but have %s" %
                                     (entry.get("name"),
                                      nevra2string(nevra),
                                      nevra2string(all_pkg_objs[0])))
                entry.set('version', "%s:%s-%s.%s" %
                          (nevra.get('epoch', 'any'),
                           nevra.get('version', 'any'),
                           nevra.get('release', 'any'),
                           nevra.get('arch', 'any')))
                qtext_versions.append("U(%s)" % str(all_pkg_objs[0]))
                continue

            if self.setup.get('quick', False):
                # Passed -q on the command line
                continue
            if not (pkg_verify and
                    inst.get('pkg_verify', 'true').lower() == 'true'):
                continue

            # XXX: We ignore GPG sig checking the package as it
            # has nothing to do with the individual file hash/size/etc.
            # GPG checking the package only eaxmines some header/rpmdb
            # wacky-ness, and will not properly detect a compromised rpmdb.
            # Yum's verify routine does not support it for that reaosn.

            if len(pkg_objs) > 1:
                self.logger.debug("  Verify Instance found many packages:")
                for pkg in pkg_objs:
                    self.logger.debug("    %s" % str(pkg))

            try:
                vrfy_result = self._verifyHelper(pkg_objs[0])
            except:  # pylint: disable=W0702
                err = sys.exc_info()[1]
                # Unknown Yum exception
                self.logger.warning("  Verify Exception: %s" % err)
                package_fail = True
                continue

            # Now take out the Yum specific objects / modlists / unproblems
            ignores = [ig.get('name') for ig in entry.findall('Ignore')] + \
                [ig.get('name') for ig in inst.findall('Ignore')] + \
                self.ignores
            for fname, probs in list(vrfy_result.items()):
                if fname in modlist:
                    self.logger.debug("  %s in modlist, skipping" % fname)
                    continue
                if fname in ignores:
                    self.logger.debug("  %s in ignore list, skipping" % fname)
                    continue
                tmp = []
                for prob in probs:
                    if prob.type == 'missing' and os.path.islink(fname):
                        continue
                    elif 'no' + prob.type in verify_flags:
                        continue
                    if prob.type not in ['missingok', 'ghost']:
                        tmp.append((prob.type, prob.message))
                if tmp != []:
                    stat['verify'][fname] = tmp

            if stat['verify'] != {}:
                stat['verify_fail'] = True
                package_fail = True
                self.logger.info("It is suggested that you either manage "
                                 "these files, revert the changes, or ignore "
                                 "false failures:")
                self.logger.info("  Verify Problems: %s" %
                                 stat['pkg'].get('name'))
                for fname, probs in list(stat['verify'].items()):
                    if len(probs) > 1:
                        self.logger.info("    %s" % fname)
                        for prob in probs:
                            self.logger.info("      %s" % prob[1])
                    else:
                        self.logger.info("    %s: %s" % (fname, probs[0]))

        if len(all_pkg_objs) > 0:
            # Is this an install only package?  We just look at the first one
            provides = set([p[0] for p in all_pkg_objs[0].provides] +
                           [all_pkg_objs[0].name])
            install_only = len(set(self.installonlypkgs) & provides) > 0
        else:
            install_only = False

        if virt_pkg or \
           (install_only and not self.setup['kevlar']) or \
           yum_group:
            # virtual capability supplied, we are probably dealing
            # with multiple packages of different names.  This check
            # doesn't make a lot of since in this case.
            # install_only: Yum may clean some of these up itself.
            # Otherwise having multiple instances of install only packages
            # is considered correct
            self.extra_instances = None
        else:
            self.extra_instances = self.FindExtraInstances(entry, all_pkg_objs)
        if self.extra_instances is not None:
            package_fail = True

        return not package_fail
    # pylint: enable=R0914,R0912,R0915

    def FindExtraInstances(self, entry, all_pkg_objs):
        """ Check for installed instances that are not in the
        config. Return a Package Entry with Instances to remove, or
        None if there are no Instances to remove. """
        if len(all_pkg_objs) == 0:
            return None
        name = entry.get('name')
        extra_entry = Bcfg2.Client.XML.Element('Package', name=name,
                                               type=self.pkgtype)
        instances = self._buildInstances(entry)
        pkg_objs = [p for p in all_pkg_objs]  # Shallow copy

        # Algorythm is sensitive to duplicates, check for them
        checked = []
        for inst in instances:
            nevra = build_yname(name, inst)
            pkgs = self.yumbase.rpmdb.searchNevra(**short_yname(nevra))
            if len(pkgs) > 0:
                if pkgs[0] in checked:
                    continue  # We've already taken care of this Instance
                else:
                    checked.append(pkgs[0])
                pkg_objs.remove(pkgs[0])

        for pkg in pkg_objs:
            self.logger.debug("  Extra Instance Found: %s" % str(pkg))
            Bcfg2.Client.XML.SubElement(extra_entry, 'Instance',
                                        epoch=pkg.epoch, name=pkg.name,
                                        version=pkg.version,
                                        release=pkg.release, arch=pkg.arch)

        if pkg_objs == []:
            return None
        else:
            return extra_entry

    def FindExtra(self):
        """Find extra packages."""
        packages = [e.get('name') for e in self.getSupportedEntries()]
        extras = []

        for pkg in list(self.installed.keys()):
            if pkg not in packages:
                entry = Bcfg2.Client.XML.Element('Package', name=pkg,
                                                 type=self.pkgtype)
                for i in self.installed[pkg]:
                    Bcfg2.Client.XML.SubElement(entry, 'Instance',
                                                epoch=i['epoch'],
                                                version=i['version'],
                                                release=i['release'],
                                                arch=i['arch'])

                extras.append(entry)

        return extras

    def _installGPGKey(self, inst, key_file):
        """Examine the GPG keys carefully before installation.  Avoid
           installing duplicate keys.  Returns True on successful install."""

        # RPM Transaction Set
        tset = self.yumbase.rpmdb.readOnlyTS()

        if not os.path.exists(key_file):
            self.logger.debug("GPG Key file %s not installed" % key_file)
            return False

        rawkey = open(key_file).read()
        gpg = yum.misc.getgpgkeyinfo(rawkey)

        ver = yum.misc.keyIdToRPMVer(gpg['keyid'])
        rel = yum.misc.keyIdToRPMVer(gpg['timestamp'])
        if not (ver == inst.get('version') and rel == inst.get('release')):
            self.logger.info("GPG key file %s does not match gpg-pubkey-%s-%s"
                             % (key_file, inst.get('version'),
                                inst.get('release')))
            return False

        if not yum.misc.keyInstalled(tset, gpg['keyid'],
                                     gpg['timestamp']) == 0:
            result = tset.pgpImportPubkey(yum.misc.procgpgkey(rawkey))
        else:
            self.logger.debug("gpg-pubkey-%s-%s already installed" %
                              (inst.get('version'), inst.get('release')))
            return True

        if result != 0:
            self.logger.debug(
                "Unable to install %s-%s" %
                (self.instance_status[inst].get('pkg').get('name'),
                 nevra2string(inst)))
            return False
        else:
            self.logger.debug(
                "Installed %s-%s-%s" %
                (self.instance_status[inst].get('pkg').get('name'),
                 inst.get('version'), inst.get('release')))
            return True

    def _runYumTransaction(self):
        """ run the yum transaction that has already been set up """
        def cleanup():
            """ clean up open stuff when we hit an error """
            self.yumbase.closeRpmDB()
            self.RefreshPackages()

        rpm_display = RPMDisplay(self.logger)
        yum_display = YumDisplay(self.logger)
        # Run the Yum Transaction
        try:
            rescode, restring = self.yumbase.buildTransaction()
        except yum.Errors.YumBaseError:
            err = sys.exc_info()[1]
            self.logger.error("Error building Yum transaction: %s" % err)
            cleanup()
            return

        self.logger.debug("Initial Yum buildTransaction() run said:")
        self.logger.debug("   resultcode: %s, msgs: %s" %
                          (rescode, restring))

        if rescode != 1:
            # Transaction built successfully, run it
            try:
                self.yumbase.processTransaction(callback=yum_display,
                                                rpmDisplay=rpm_display)
                self.logger.info("Single Pass for Install Succeeded")
            except yum.Errors.YumBaseError:
                err = sys.exc_info()[1]
                self.logger.error("Error processing Yum transaction: %s" % err)
                cleanup()
                return
        else:
            # The yum command failed.  No packages installed.
            # Try installing instances individually.
            self.logger.error("Single Pass Install of Packages Failed")
            skip_broken = self.yumbase.conf.skip_broken
            self.yumbase.conf.skip_broken = True
            try:
                rescode, restring = self.yumbase.buildTransaction()
                if rescode != 1:
                    self.yumbase.processTransaction(callback=yum_display,
                                                    rpmDisplay=rpm_display)
                    self.logger.debug(
                        "Second pass install did not install all packages")
                else:
                    self.logger.error("Second pass yum install failed.")
                    self.logger.debug("   %s" % restring)
            except yum.Errors.YumBaseError:
                err = sys.exc_info()[1]
                self.logger.error("Error rerunning Yum transaction: %s" % err)

            self.yumbase.conf.skip_broken = skip_broken

        cleanup()

    def Install(self, packages, states):  # pylint: disable=R0912,R0914
        """ Try and fix everything that Yum.VerifyPackages() found
        wrong for each Package Entry.  This can result in individual
        RPMs being installed (for the first time), deleted, downgraded
        or upgraded.

        packages is a list of Package Elements that has
        states[<Package Element>] == False

        The following effects occur:
           - states{} is conditionally updated for each package.
           - self.installed{} is rebuilt, possibly multiple times.
           - self.instance_status{} is conditionally updated for each instance
             of a package.
           - Each package will be added to self.modified[] if its states{}
             entry is set to True. """
        self.logger.debug('Running Yum.Install()')

        install_pkgs = []
        gpg_keys = []
        upgrade_pkgs = []
        reinstall_pkgs = []

        def queue_pkg(pkg, inst, queue):
            """ add a package to the appropriate work queue --
            packages to install, packages to upgrade, etc. """
            if pkg.get('name') == 'gpg-pubkey':
                gpg_keys.append(inst)
            else:
                queue.append(inst)

        # Remove extra instances.
        # Can not reverify because we don't have a package entry.
        if self.extra_instances is not None and len(self.extra_instances) > 0:
            if (self.setup.get('remove') == 'all' or
                self.setup.get('remove') == 'packages'):
                self.Remove(self.extra_instances)
            else:
                self.logger.info("The following extra package instances will "
                                 "be removed by the '-r' option:")
                for pkg in self.extra_instances:
                    for inst in pkg:
                        self.logger.info("    %s %s" %
                                         ((pkg.get('name'),
                                           nevra2string(inst))))

        # Figure out which instances of the packages actually need something
        # doing to them and place in the appropriate work 'queue'.
        for pkg in packages:
            insts = [pinst for pinst in pkg
                     if pinst.tag in ['Instance', 'Package']]
            if insts:
                for inst in insts:
                    if inst not in self.instance_status:
                        self.logger.warning(
                            "  Asked to install/update package never "
                            "verified: %s" %
                            nevra2string(build_yname(pkg.get('name'), inst)))
                        continue
                    status = self.instance_status[inst]
                    if not status.get('installed', False) and self.do_install:
                        queue_pkg(pkg, inst, install_pkgs)
                    elif status.get('version_fail', False) and self.do_upgrade:
                        queue_pkg(pkg, inst, upgrade_pkgs)
                    elif status.get('verify_fail', False) and self.do_reinst:
                        queue_pkg(pkg, inst, reinstall_pkgs)
                    else:
                        # Either there was no Install/Version/Verify
                        # task to be done or the user disabled the actions
                        # in the configuration.  XXX Logging for the latter?
                        pass
            else:
                msg = "Yum: Package tag found where Instance expected: %s"
                self.logger.warning(msg % pkg.get('name'))
                queue_pkg(pkg, pkg, install_pkgs)

        # Install GPG keys.
        # Alternatively specify the required keys using 'gpgkey' in the
        # repository definition in yum.conf.  YUM will install the keys
        # automatically.
        if len(gpg_keys) > 0:
            self.logger.info("Installing GPG keys.")
            for inst in gpg_keys:
                if inst.get('simplefile') is None:
                    self.logger.error("GPG key has no simplefile attribute")
                    continue
                key_file = os.path.join(
                    self.instance_status[inst].get('pkg').get('uri'),
                    inst.get('simplefile'))
                self._installGPGKey(inst, key_file)

            self.RefreshPackages()
            pkg = self.instance_status[gpg_keys[0]].get('pkg')
            states[pkg] = self.VerifyPackage(pkg, [])

        # We want to reload all Yum configuration in case we've
        # deployed new .repo files we should consider
        self._loadYumBase()

        # Install packages.
        if len(install_pkgs) > 0:
            self.logger.info("Attempting to install packages")

            for inst in install_pkgs:
                pkg_arg = self.instance_status[inst].get('pkg').get('name')
                self.logger.debug("Installing %s" % pkg_arg)
                try:
                    self.yumbase.install(**build_yname(pkg_arg, inst))
                except yum.Errors.YumBaseError:
                    yume = sys.exc_info()[1]
                    self.logger.error("Error installing package %s: %s" %
                                      (pkg_arg, yume))

        if len(upgrade_pkgs) > 0:
            self.logger.info("Attempting to upgrade packages")

            for inst in upgrade_pkgs:
                pkg_arg = self.instance_status[inst].get('pkg').get('name')
                self.logger.debug("Upgrading %s" % pkg_arg)
                try:
                    self.yumbase.update(**build_yname(pkg_arg, inst))
                except yum.Errors.YumBaseError:
                    yume = sys.exc_info()[1]
                    self.logger.error("Error upgrading package %s: %s" %
                                      (pkg_arg, yume))

        if len(reinstall_pkgs) > 0:
            self.logger.info("Attempting to reinstall packages")
            for inst in reinstall_pkgs:
                pkg_arg = self.instance_status[inst].get('pkg').get('name')
                self.logger.debug("Reinstalling %s" % pkg_arg)
                try:
                    self.yumbase.reinstall(**build_yname(pkg_arg, inst))
                except yum.Errors.YumBaseError:
                    yume = sys.exc_info()[1]
                    self.logger.error("Error reinstalling package %s: %s" %
                                      (pkg_arg, yume))

        self._runYumTransaction()

        if not self.setup['kevlar']:
            for pkg_entry in [p for p in packages if self.canVerify(p)]:
                self.logger.debug("Reverifying Failed Package %s" %
                                  pkg_entry.get('name'))
                states[pkg_entry] = \
                    self.VerifyPackage(pkg_entry,
                                       self.modlists.get(pkg_entry, []))

        for entry in [ent for ent in packages if states[ent]]:
            self.modified.append(entry)

    def Remove(self, packages):
        """
           Remove specified entries.

           packages is a list of Package Entries with Instances generated
           by FindExtra().
        """
        self.logger.debug('Running Yum.Remove()')

        for pkg in packages:
            for inst in pkg:
                nevra = build_yname(pkg.get('name'), inst)
                if pkg.get('name') != 'gpg-pubkey':
                    self.yumbase.remove(**nevra)
                    self.modified.append(pkg)
                else:
                    self.logger.info("WARNING: gpg-pubkey package not in "
                                     "configuration %s %s-%s" %
                                     (nevra['name'], nevra['version'],
                                      nevra['release']))

        self._runYumTransaction()
        self.extra = self.FindExtra()

    def VerifyPath(self, entry, _):  # pylint: disable=W0613
        """Do nothing here since we only verify Path type=ignore"""
        return True
