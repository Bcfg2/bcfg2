"""This provides bcfg2 support for yum."""
__revision__ = '$Revision$'

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
# Compatibility import
from Bcfg2.Bcfg2Py3k import ConfigParser

# Fix for python2.3
try:
    set
except NameError:
    from sets import Set as set


def build_yname(pkgname, inst):
    """Build yum appropriate package name."""
    d = {}
    if isinstance(inst, yum.packages.PackageObject):
        for i in ['name', 'epoch', 'version', 'release', 'arch']:
            d[i] = getattr(inst, i)
    else:
        d['name'] = pkgname
        if inst.get('version') != 'any':
            d['version'] = inst.get('version')
        if inst.get('epoch', False):
            d['epoch'] = inst.get('epoch')
        if inst.get('release', False) and inst.get('release') != 'any':
            d['release'] = inst.get('release')
        if inst.get('arch', False) and inst.get('arch') != 'any':
            d['arch'] = inst.get('arch')
    return d


def short_yname(nevra):
    d = nevra.copy()
    if 'version' in d:
        d['ver'] = d['version']
        del d['version']
    if 'release' in d:
        d['rel'] = d['release']
        del d['release']
    return d


def nevraString(p):
    if isinstance(p, yum.packages.PackageObject):
        return str(p)
    else:
        ret = ""
        for i, j in [('epoch', '%s:'), ('name', '%s'), ('version', '-%s'),
                     ('release', '-%s'), ('arch', '.%s')]:
            if i in p:
                ret = "%s%s" % (ret, j % p[i])
        return ret


class Parser(ConfigParser.ConfigParser):

    def get(self, section, option, default):
        """
        Override ConfigParser.get: If the request option is not in the
        config file then return the value of default rather than raise
        an exception.  We still raise exceptions on missing sections.
        """
        try:
            return ConfigParser.ConfigParser.get(self, section, option)
        except (ConfigParser.NoOptionError, ConfigParser.NoSectionError):
            return default


class RPMDisplay(yum.rpmtrans.RPMBaseCallback):
    """We subclass the default RPM transaction callback so that we
       can control Yum's verbosity and pipe it through the right logger."""

    def __init__(self, logger):
        yum.rpmtrans.RPMBaseCallback.__init__(self)
        self.logger = logger
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
            msg = "%s: %s" % (self.action[action], package)
            self.logger.info(msg)
            self.state = action
            self.package = str(package)

    def scriptout(self, package, msgs):
        """Handle output from package scripts."""

        if msgs:
            msg = "%s: %s" % (package, msgs)
            self.logger.debug(msg)

    def errorlog(self, msg):
        """Deal with error reporting."""
        self.logger.error(msg)


class YumDisplay(yum.callbacks.ProcessTransBaseCallback):
    """Class to handle display of what step we are in the Yum transaction
       such as downloading packages, etc."""

    def __init__(self, logger):
        self.logger = logger


class YUMng(Bcfg2.Client.Tools.PkgTool):
    """Support for Yum packages."""
    pkgtype = 'yum'

    name = 'YUMng'
    __execs__ = []
    __handles__ = [('Package', 'yum'),
                   ('Package', 'rpm'),
                   ('Path', 'ignore')]

    __req__ = {'Package': ['name'],
               'Path': ['type']}
    __ireq__ = {'Package': ['name']}

    conflicts = ['YUM24', 'RPMng']

    def __init__(self, logger, setup, config):
        self.yb = yum.YumBase()

        if setup['debug']:
            debuglevel = 3
        elif setup['verbose']:
            debuglevel = 2
        else:
            debuglevel = 1

        try:
            self.yb.preconf.debuglevel = debuglevel
        except AttributeError:
            self.yb._getConfig(self.yb.config_file_path,
                               debuglevel=debuglevel)

        Bcfg2.Client.Tools.PkgTool.__init__(self, logger, setup, config)
        self.ignores = [entry.get('name') for struct in config \
                        for entry in struct \
                        if entry.tag == 'Path' and \
                        entry.get('type') == 'ignore']
        self.instance_status = {}
        self.extra_instances = []
        self.modlists = {}
        self._loadConfig()
        self.__important__ = self.__important__ + \
                             [entry.get('name') for struct in config \
                              for entry in struct \
                              if entry.tag == 'Path' and \
                              (entry.get('name').startswith('/etc/yum.d') \
                              or entry.get('name').startswith('/etc/yum.repos.d')) \
                              or entry.get('name') == '/etc/yum.conf']
        self.yum_avail = dict()
        self.yum_installed = dict()
        try:
            self.yb.doConfigSetup()
            self.yb.doTsSetup()
            self.yb.doRpmDBSetup()
        except yum.Errors.RepoError:
            e = sys.exc_info()[1]
            self.logger.error("YUMng Repository error: %s" % e)
            raise Bcfg2.Client.Tools.toolInstantiationError
        except Exception:
            e = sys.exc_info()[1]
            self.logger.error("YUMng error: %s" % e)
            raise Bcfg2.Client.Tools.toolInstantiationError

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
                    data = [(pkg.arch, (pkg.epoch, pkg.version, pkg.release))]
                else:
                    pname = pkg[0]
                    data = [(pkg[1], (pkg[2], pkg[3], pkg[4]))]
                if pname in dest:
                    dest[pname].update(data)
                else:
                    dest[pname] = dict(data)

    def _loadConfig(self):
        # Process the YUMng section from the config file.
        CP = Parser()
        CP.read(self.setup.get('setup'))
        truth = ['true', 'yes', '1']

        # These are all boolean flags, either we do stuff or we don't
        self.pkg_checks = CP.get(self.name, "pkg_checks", "true").lower() \
                in truth
        self.pkg_verify = CP.get(self.name, "pkg_verify", "true").lower() \
                in truth
        self.doInstall = CP.get(self.name, "installed_action",
                "install").lower() == "install"
        self.doUpgrade = CP.get(self.name,
                "version_fail_action", "upgrade").lower() == "upgrade"
        self.doReinst = CP.get(self.name, "verify_fail_action",
                "reinstall").lower() == "reinstall"
        self.verifyFlags = CP.get(self.name, "verify_flags",
                                  "").lower().replace(' ', ',')

        self.installOnlyPkgs = self.yb.conf.installonlypkgs
        if 'gpg-pubkey' not in self.installOnlyPkgs:
            self.installOnlyPkgs.append('gpg-pubkey')

        self.logger.debug("YUMng: Install missing: %s" \
                % self.doInstall)
        self.logger.debug("YUMng: pkg_checks: %s" % self.pkg_checks)
        self.logger.debug("YUMng: pkg_verify: %s" % self.pkg_verify)
        self.logger.debug("YUMng: Upgrade on version fail: %s" \
                % self.doUpgrade)
        self.logger.debug("YUMng: Reinstall on verify fail: %s" \
                % self.doReinst)
        self.logger.debug("YUMng: installOnlyPkgs: %s" \
                % str(self.installOnlyPkgs))
        self.logger.debug("YUMng: verify_flags: %s" % self.verifyFlags)

    def _fixAutoVersion(self, entry):
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

    def _buildInstances(self, entry):
        instances = [inst for inst in entry \
                if inst.tag == 'Instance' or inst.tag == 'Package']

        # XXX: Uniquify instances.  Cases where duplicates are returned.
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

        # XXX GPG keys existing in the RPMDB have numbered days
        # and newer Yum versions will not return information about them
        if hasattr(self.yb.rpmdb, 'returnGPGPubkeyPackages'):
            return self.yb.rpmdb.returnGPGPubkeyPackages()
        return self.yb.rpmdb.searchNevra(name='gpg-pubkey')

    def _verifyHelper(self, po):
        # This code primarly deals with a yum bug where the PO.verify()
        # method does not properly take into count multilib sharing of files.
        # Neither does RPM proper, really....it just ignores the problem.
        def verify(p):
            # disabling file checksums is a new feature yum 3.2.17-ish
            try:
                vResult = p.verify(fast=self.setup.get('quick', False))
            except TypeError:
                # Older Yum API
                vResult = p.verify()
            return vResult

        key = (po.name, po.epoch, po.version, po.release, po.arch)
        if key in self.verifyCache:
            results = self.verifyCache[key]
        else:
            results = verify(po)
            self.verifyCache[key] = results
        if not rpmUtils.arch.isMultiLibArch():
            return results

        # Okay deal with a buggy yum multilib and verify
        packages = self.yb.rpmdb.searchNevra(name=po.name, epoch=po.epoch,
                ver=po.version, rel=po.release)  # find all arches of pkg
        if len(packages) == 1:
            return results      # No mathcing multilib packages

        files = set(po.returnFileEntries())   # Will be the list of common fns
        common = {}
        for p in packages:
            if p != po:
                files = files & set(p.returnFileEntries())
        for p in packages:
            k = (p.name, p.epoch, p.version, p.release, p.arch)
            self.logger.debug("Multilib Verify: comparing %s to %s" \
                    % (po, p))
            if k in self.verifyCache:
                v = self.verifyCache[k]
            else:
                v = verify(p)
                self.verifyCache[k] = v

            for fn, probs in list(v.items()):
                # file problems must exist in ALL multilib packages to be real
                if fn in files:
                    common[fn] = common.get(fn, 0) + 1

        flag = len(packages) - 1
        for fn, i in list(common.items()):
            if i == flag:
                # this fn had verify problems in all but one of the multilib
                # packages.  That means its correct in the package that's
                # "on top."  Therefore, this is a fake verify problem.
                if fn in results:
                    del results[fn]

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
                   self.yb.rpmdb.returnPackages()
        for po in packages:
            d = {}
            for i in ['name', 'epoch', 'version', 'release', 'arch']:
                if i == 'arch' and getattr(po, i) is None:
                    d[i] = 'noarch'
                elif i == 'epoch' and getattr(po, i) is None:
                    d[i] = '0'
                else:
                    d[i] = getattr(po, i)
            self.installed.setdefault(po.name, []).append(d)

    def VerifyPackage(self, entry, modlist, pinned_version=None):
        """
            Verify Package status for entry.
            Performs the following:
                - Checks for the presence of required Package Instances.
                - Compares the evra 'version' info against self.installed{}.
                - RPM level package verify (rpm --verify).
                - Checks for the presence of unrequired package instances.

            Produces the following dict and list for YUMng.Install() to use:
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

        if entry.get('version', False) == 'auto':
            self._fixAutoVersion(entry)

        self.logger.debug("Verifying package instances for %s" \
                % entry.get('name'))

        self.verifyCache = {}            # Used for checking multilib packages
        self.modlists[entry] = modlist
        instances = self._buildInstances(entry)
        packageCache = []
        package_fail = False
        qtext_versions = []
        virtPkg = False
        pkg_checks = self.pkg_checks and \
                entry.get('pkg_checks', 'true').lower() == 'true'
        pkg_verify = self.pkg_verify and \
                entry.get('pkg_verify', 'true').lower() == 'true'

        if entry.get('name') == 'gpg-pubkey':
            POs = self._getGPGKeysAsPackages()
            pkg_verify = False  # No files here to verify
        else:
            POs = self.yb.rpmdb.searchNevra(name=entry.get('name'))
        if len(POs) == 0:
            # Some sort of virtual capability?  Try to resolve it
            POs = self.yb.rpmdb.searchProvides(entry.get('name'))
            if len(POs) > 0:
                virtPkg = True
                self.logger.info("%s appears to be provided by:" \
                                 % entry.get('name'))
                for p in POs:
                    self.logger.info("  %s" % p)

        for inst in instances:
            nevra = build_yname(entry.get('name'), inst)
            snevra = short_yname(nevra)
            if nevra in packageCache:
                continue   # Ignore duplicate instances
            else:
                packageCache.append(nevra)

            self.logger.debug("Verifying: %s" % nevraString(nevra))

            # Set some defaults here
            stat = self.instance_status.setdefault(inst, {})
            stat['installed'] = True
            stat['version_fail'] = False
            stat['verify'] = {}
            stat['verify_fail'] = False
            stat['pkg'] = entry
            stat['modlist'] = modlist
            verify_flags = inst.get('verify_flags', self.verifyFlags)
            verify_flags = verify_flags.lower().replace(' ', ',').split(',')

            if 'arch' in nevra:
                # If arch is specified use it to select the package
                _POs = [ p for p in POs if p.arch == nevra['arch'] ]
            else:
                _POs = POs
            if len(_POs) == 0:
                # Package (name, arch) not installed
                self.logger.debug("  %s is not installed" % nevraString(nevra))
                stat['installed'] = False
                package_fail = True
                qtext_versions.append("I(%s)" % nevra)
                continue

            if not pkg_checks:
                continue

            # Check EVR
            if virtPkg:
                self.logger.debug("  Not checking version for virtual package")
                _POs = [po for po in POs]  # Make a copy
            elif entry.get('name') == 'gpg-pubkey':
                if 'version' not in nevra:
                    m = "Skipping verify: gpg-pubkey without an RPM version."
                    self.logger.warning(m)
                    continue
                if 'release' not in nevra:
                    m = "Skipping verify: gpg-pubkey without an RPM release."
                    self.logger.warning(m)
                    continue
                _POs = [p for p in POs if p.version == nevra['version'] \
                        and p.release == nevra['release']]
            else:
                _POs = self.yb.rpmdb.searchNevra(**snevra)
            if len(_POs) == 0:
                package_fail = True
                stat['version_fail'] = True
                # Just chose the first pkg for the error message
                self.logger.info("  %s: Wrong version installed.  "
                                 "Want %s, but have %s" % (entry.get("name"),
                                                           nevraString(nevra),
                                                           nevraString(POs[0])))
                qtext_versions.append("U(%s)" % str(POs[0]))
                continue

            if self.setup.get('quick', False):
                # Passed -q on the command line
                continue
            if not (pkg_verify and \
                    inst.get('pkg_verify', 'true').lower() == 'true'):
                continue

            # XXX: We ignore GPG sig checking the package as it
            # has nothing to do with the individual file hash/size/etc.
            # GPG checking the package only eaxmines some header/rpmdb
            # wacky-ness, and will not properly detect a compromised rpmdb.
            # Yum's verify routine does not support it for that reaosn.

            if len(_POs) > 1:
                self.logger.debug("  Verify Instance found many packages:")
                for po in _POs:
                    self.logger.debug("    %s" % str(po))

            try:
                vResult = self._verifyHelper(_POs[0])
            except Exception:
                e = sys.exc_info()[1]
                # Unknown Yum exception
                self.logger.warning("  Verify Exception: %s" % str(e))
                package_fail = True
                continue

            # Now take out the Yum specific objects / modlists / unproblmes
            ignores = [ig.get('name') for ig in entry.findall('Ignore')] + \
                      [ig.get('name') for ig in inst.findall('Ignore')] + \
                      self.ignores
            for fn, probs in list(vResult.items()):
                if fn in modlist:
                    self.logger.debug("  %s in modlist, skipping" % fn)
                    continue
                if fn in ignores:
                    self.logger.debug("  %s in ignore list, skipping" % fn)
                    continue
                tmp = []
                for p in probs:
                    if p.type == 'missing' and os.path.islink(fn):
                        continue
                    elif 'no' + p.type in verify_flags:
                        continue
                    if p.type not in ['missingok', 'ghost']:
                        tmp.append((p.type, p.message))
                if tmp != []:
                    stat['verify'][fn] = tmp

            if stat['verify'] != {}:
                stat['verify_fail'] = True
                package_fail = True
                self.logger.debug("It is suggested that you either manage "
                                  "these files, revert the changes, or ignore "
                                  "false failures:")
                self.logger.debug("  Verify Problems:")
                for fn, probs in list(stat['verify'].items()):
                    self.logger.debug("    %s" % fn)
                    for p in probs:
                        self.logger.debug("      %s: %s" % p)

        if len(POs) > 0:
            # Is this an install only package?  We just look at the first one
            provides = set([p[0] for p in POs[0].provides] + [POs[0].name])
            install_only = len(set(self.installOnlyPkgs) & provides) > 0
        else:
            install_only = False

        if virtPkg or (install_only and not self.setup['kevlar']):
            # XXX: virtual capability supplied, we a probably dealing
            # with multiple packages of different names.  This check
            # doesn't make a lot of since in this case
            # XXX: install_only: Yum may clean some of these up itself.
            # Otherwise having multiple instances of install only packages
            # is considered correct
            self.extra_instances = None
        else:
            self.extra_instances = self.FindExtraInstances(entry, POs)
        if self.extra_instances is not None:
            package_fail = True

        return not package_fail

    def FindExtraInstances(self, entry, POs):
        """
            Check for installed instances that are not in the config.
            Return a Package Entry with Instances to remove, or None if there
            are no Instances to remove.

        """
        if len(POs) == 0:
            return None
        name = entry.get('name')
        extra_entry = Bcfg2.Client.XML.Element('Package', name=name,
                                               type=self.pkgtype)
        instances = self._buildInstances(entry)
        _POs = [p for p in POs]  # Shallow copy

        # Algorythm is sensitive to duplicates, check for them
        checked = []
        for inst in instances:
            nevra = build_yname(name, inst)
            snevra = short_yname(nevra)
            pkgs = self.yb.rpmdb.searchNevra(**snevra)
            flag = True
            if len(pkgs) > 0:
                if pkgs[0] in checked:
                    continue  # We've already taken care of this Instance
                else:
                    checked.append(pkgs[0])
                _POs.remove(pkgs[0])

        for p in _POs:
            self.logger.debug("  Extra Instance Found: %s" % str(p))
            Bcfg2.Client.XML.SubElement(extra_entry, 'Instance',
                    epoch=p.epoch, name=p.name, version=p.version,
                    release=p.release, arch=p.arch)

        if _POs == []:
            return None
        else:
            return extra_entry

    def FindExtraPackages(self):
        """Find extra packages."""
        packages = [e.get('name') for e in self.getSupportedEntries()]
        extras = []

        for p in list(self.installed.keys()):
            if p not in packages:
                entry = Bcfg2.Client.XML.Element('Package', name=p,
                                                 type=self.pkgtype)
                for i in self.installed[p]:
                    inst = Bcfg2.Client.XML.SubElement(entry,
                                                       'Instance',
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
        ts = self.yb.rpmdb.readOnlyTS()

        if not os.path.exists(key_file):
            self.logger.debug("GPG Key file %s not installed" % key_file)
            return False

        rawkey = open(key_file).read()
        gpg = yum.misc.getgpgkeyinfo(rawkey)

        ver = yum.misc.keyIdToRPMVer(gpg['keyid'])
        rel = yum.misc.keyIdToRPMVer(gpg['timestamp'])
        if not (ver == inst.get('version') and rel == inst.get('release')):
            self.logger.info("GPG key file %s does not match gpg-pubkey-%s-%s"\
                             % (key_file, inst.get('version'),
                                inst.get('release')))
            return False

        if not yum.misc.keyInstalled(ts, gpg['keyid'],
                                     gpg['timestamp']) == 0:
            result = ts.pgpImportPubkey(yum.misc.procgpgkey(rawkey))
        else:
            self.logger.debug("gpg-pubkey-%s-%s already installed"\
                              % (inst.get('version'),
                                 inst.get('release')))
            return True

        if result != 0:
            self.logger.debug("Unable to install %s-%s" % \
                        (self.instance_status[inst].get('pkg').get('name'),
                         self.str_evra(inst)))
            return False
        else:
            self.logger.debug("Installed %s-%s-%s" % \
                        (self.instance_status[inst].get('pkg').get('name'),
                         inst.get('version'), inst.get('release')))
            return True

    def _runYumTransaction(self):
        def cleanup():
            self.yb.closeRpmDB()
            self.RefreshPackages()

        rDisplay = RPMDisplay(self.logger)
        yDisplay = YumDisplay(self.logger)
        # Run the Yum Transaction
        try:
            rescode, restring = self.yb.buildTransaction()
        except yum.Errors.YumBaseError:
            e = sys.exc_info()[1]
            self.logger.error("Yum transaction error: %s" % str(e))
            cleanup()
            return

        self.logger.debug("Initial Yum buildTransaction() run said:")
        self.logger.debug("   resultcode: %s, msgs: %s" \
                          % (rescode, restring))

        if rescode != 1:
            # Transaction built successfully, run it
            try:
                self.yb.processTransaction(callback=yDisplay,
                                           rpmDisplay=rDisplay)
                self.logger.info("Single Pass for Install Succeeded")
            except yum.Errors.YumBaseError:
                e = sys.exc_info()[1]
                self.logger.error("Yum transaction error: %s" % str(e))
                cleanup()
                return
        else:
            # The yum command failed.  No packages installed.
            # Try installing instances individually.
            self.logger.error("Single Pass Install of Packages Failed")
            skipBroken = self.yb.conf.skip_broken
            self.yb.conf.skip_broken = True
            try:
                rescode, restring = self.yb.buildTransaction()
                if rescode != 1:
                    self.yb.processTransaction(callback=yDisplay,
                                               rpmDisplay=rDisplay)
                    self.logger.debug(
                        "Second pass install did not install all packages")
                else:
                    self.logger.error("Second pass yum install failed.")
                    self.logger.debug("   %s" % restring)
            except yum.Errors.YumBaseError, e:
                self.logger.error("Yum transaction error: %s" % str(e))

            self.yb.conf.skip_broken = skipBroken

        cleanup()

    def Install(self, packages, states):
        """
           Try and fix everything that YUMng.VerifyPackages() found wrong for
           each Package Entry.  This can result in individual RPMs being
           installed (for the first time), deleted, downgraded
           or upgraded.

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
        self.logger.debug('Running YUMng.Install()')

        install_pkgs = []
        gpg_keys = []
        upgrade_pkgs = []
        reinstall_pkgs = []

        def queuePkg(pkg, inst, queue):
            if pkg.get('name') == 'gpg-pubkey':
                gpg_keys.append(inst)
            else:
                queue.append(inst)

        # Remove extra instances.
        # Can not reverify because we don't have a package entry.
        if self.extra_instances is not None and len(self.extra_instances) > 0:
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
                    if inst not in self.instance_status:
                        m = "  Asked to install/update package never verified"
                        p = nevraString(build_yname(pkg.get('name'), inst))
                        self.logger.warning("%s: %s" % (m, p))
                        continue
                    status = self.instance_status[inst]
                    if not status.get('installed', False) and self.doInstall:
                        queuePkg(pkg, inst, install_pkgs)
                    elif status.get('version_fail', False) and self.doUpgrade:
                        queuePkg(pkg, inst, upgrade_pkgs)
                    elif status.get('verify_fail', False) and self.doReinst:
                        queuePkg(pkg, inst, reinstall_pkgs)
                    else:
                        # Either there was no Install/Version/Verify
                        # task to be done or the user disabled the actions
                        # in the configuration.  XXX Logging for the latter?
                        pass
            else:
                msg = "YUMng: Package tag found where Instance expected: %s"
                self.logger.warning(msg % pkg.get('name'))
                queuePkg(pkg, pkg, install_pkgs)

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
                key_file = os.path.join(self.instance_status[inst].get('pkg').get('uri'), \
                                                     inst.get('simplefile'))
                self._installGPGKey(inst, key_file)

            self.RefreshPackages()
            pkg = self.instance_status[gpg_keys[0]].get('pkg')
            states[pkg] = self.VerifyPackage(pkg, [])

        # Install packages.
        if len(install_pkgs) > 0:
            self.logger.info("Attempting to install packages")

            for inst in install_pkgs:
                pkg_arg = self.instance_status[inst].get('pkg').get('name')
                self.logger.debug("Installing %s" % pkg_arg)
                try:
                    self.yb.install(**build_yname(pkg_arg, inst))
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
                    self.yb.update(**build_yname(pkg_arg, inst))
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
                    self.yb.reinstall(**build_yname(pkg_arg, inst))
                except yum.Errors.YumBaseError:
                    yume = sys.exc_info()[1]
                    self.logger.error("Error reinstalling package %s: %s" %
                                      (pkg_arg, yume))

        self._runYumTransaction()

        if not self.setup['kevlar']:
            for pkg_entry in [p for p in packages if self.canVerify(p)]:
                self.logger.debug("Reverifying Failed Package %s" \
                        % (pkg_entry.get('name')))
                states[pkg_entry] = self.VerifyPackage(pkg_entry,
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

        erase_args = []
        for pkg in packages:
            for inst in pkg:
                nevra = build_yname(pkg.get('name'), inst)
                if pkg.get('name') != 'gpg-pubkey':
                    self.yb.remove(**nevra)
                    self.modified.append(pkg)
                else:
                    self.logger.info("WARNING: gpg-pubkey package not in configuration %s %s-%s"\
                         % (nevra['name'], nevra['version'], nevra['release']))
                    self.logger.info("   This package will be deleted in a future version of the YUMng driver.")

        self._runYumTransaction()
        self.extra = self.FindExtraPackages()

    def VerifyPath(self, entry, _):
        """Do nothing here since we only verify Path type=ignore"""
        return True
