import os
import re
import sys
import glob
from subprocess import Popen, PIPE, STDOUT

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
_path = os.path.dirname(__file__)
while _path != '/':
    if os.path.basename(_path).lower().startswith("test"):
        sys.path.append(_path)
    if os.path.basename(_path) == "testsuite":
        break
    _path = os.path.dirname(_path)
from common import *

# path to Bcfg2 src directory
srcpath = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                       "src"))

# path to pylint rc file
rcfile = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                      "pylintrc.conf"))

# test for pylint existence
try:
    Popen(['pylint'], stdout=PIPE, stderr=STDOUT).wait()
    HAS_PYLINT = True
except OSError:
    HAS_PYLINT = False


# perform checks on the listed files only if the module listed in the
# keys can be imported
contingent_checks = {
    ("django",): {"lib/Bcfg2": ["Reporting"],
                  "lib/Bcfg2/Server": ["Reports",
                                       "SchemaUpdater",
                                       "models.py"],
                  "lib/Bcfg2/Server/Admin": ["Reports.py", "Syncdb.py"],
                  "sbin": ["bcfg2-reports"]},
    ("pyinotify",): {"lib/Bcfg2/Server/FileMonitor": ["Inotify.py"]},
    ("yum",): {"lib/Bcfg2/Client/Tools": ["YUM*"]},
    ("genshi",): {"lib/Bcfg2/Server/Plugins/Cfg": ["CfgGenshiGenerator.py"]},
    ("Cheetah",): {"lib/Bcfg2/Server/Plugins/Cfg": ["CfgCheetahGenerator.py"]},
    ("M2Crypto",): {"lib/Bcfg2": ["Encryption.py"],
                    "lib/Bcfg2/Server/Plugins/Cfg":
                        ["CfgEncryptedGenerator.py"]},
    ("M2Crypto", "genshi"): {"lib/Bcfg2/Server/Plugins/Cfg":
                                 ["CfgEncryptedGenshiGenerator.py"]},
    ("M2Crypto", "Cheetah"): {"lib/Bcfg2/Server/Plugins/Cfg":
                                  ["CfgEncryptedCheetahGenerator.py"]},
    }

# perform only error checking on the listed files
error_checks = {
    "sbin": ["bcfg2-build-reports", "bcfg2-reports"],
    "lib/Bcfg2": ["Proxy.py", "SSLServer.py", "Reporting"],
    "lib/Bcfg2/Server": ["Reports", "SchemaUpdater"],
    "lib/Bcfg2/Server/Admin": ["Compare.py",
                               "Snapshots.py"],
    "lib/Bcfg2/Client/Tools": ["launchd.py",
                               "OpenCSW.py",
                               "Blast.py",
                               "SYSV.py",
                               "FreeBSDInit.py",
                               "DebInit.py",
                               "RcUpdate.py",
                               "VCS.py",
                               "YUM24.py"],
    "lib/Bcfg2/Server/Plugins": ["Deps.py",
                                 "Ldap.py",
                                 "Pkgmgr.py"]
    }

# perform no checks at all on the listed files
no_checks = {
    "lib/Bcfg2/Client/Tools": ["APT.py", "RPM.py", "rpmtools.py"],
    "lib/Bcfg2/Server": ["Snapshots", "Hostbase"],
    "lib/Bcfg2": ["manage.py"],
    "lib/Bcfg2/Server/Reports": ["manage.py"],
    "lib/Bcfg2/Server/Plugins": ["Account.py",
                                 "Base.py",
                                 "Editor.py",
                                 "Hostbase.py",
                                 "Snapshots.py",
                                 "Statistics.py",
                                 "TCheetah.py",
                                 "TGenshi.py"],
    }


try:
    any
except NameError:
    def any(iterable):
        """ implementation of builtin any() for python 2.4 """
        for element in iterable:
            if element:
                return True
        return False


def expand_path_dict(pathdict):
    """ given a path dict as above, return a list of all the paths """
    rv = []
    for parent, modules in pathdict.items():
        for mod in modules:
            rv.extend(glob.glob(os.path.join(srcpath, parent, mod)))
    return rv


def whitelist_filter(filelist, whitelist):
    rv = []
    for fpath in filelist:
        if fpath in whitelist:
            rv.append(fpath)
            continue
        # check if the path is in any directories that are in the
        # whitelist
        if any(fpath.startswith(wpath + "/") for wpath in whitelist):
            rv.append(fpath)
            continue
    return rv


def blacklist_filter(filelist, blacklist):
    rv = []
    for fpath in filelist:
        if fpath in blacklist:
            continue
        # check that the path isn't in any directories that are in
        # the blacklist
        if any(fpath.startswith(bpath + "/") for bpath in blacklist):
            continue
        rv.append(fpath)
    return rv


class TestPylint(Bcfg2TestCase):
    pylint_cmd = ["pylint", "--rcfile", rcfile, "--init-hook",
                  "import sys;sys.path.append('%s')" %
                  os.path.join(srcpath, "lib")]

    # regex to find errors and fatal errors
    error_re = re.compile(r':\d+:\s+\[[EF]\d{4}')

    # build the blacklists
    blacklist = expand_path_dict(no_checks)

    contingent_blacklist = []
    for filedict in contingent_checks.values():
        contingent_blacklist += expand_path_dict(filedict)

    full_blacklist = expand_path_dict(error_checks) + contingent_blacklist + \
        blacklist

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    @skipUnless(HAS_PYLINT, "pylint not found, skipping")
    def test_lib_full(self):
        full_list = []
        for root, _, files in os.walk(os.path.join(srcpath, "lib")):
            full_list.extend(blacklist_filter([os.path.join(root, f)
                                               for f in files
                                               if f.endswith(".py")],
                                              self.full_blacklist))
        self._pylint_full(full_list)

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    @skipUnless(HAS_PYLINT, "pylint not found, skipping")
    def test_contingent_full(self):
        blacklist = set(expand_path_dict(error_checks) + self.blacklist)
        for (mods, filedict) in contingent_checks.items():
            if "django" in mods:
                # there's some issue with running pylint on modules
                # that use django in Travis CI (but not elsewhere), so
                # skip these for now
                continue
            try:
                for mod in mods:
                    __import__(mod)
            except ImportError:
                continue
            self._pylint_full(blacklist_filter(expand_path_dict(filedict),
                                               blacklist))

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    @skipUnless(HAS_PYLINT, "pylint not found, skipping")
    def test_sbin_full(self):
        all_sbin = [os.path.join(srcpath, "sbin", f)
                    for f in glob.glob(os.path.join(srcpath, "sbin", "*"))]
        sbin_list = blacklist_filter([f for f in all_sbin
                                      if not os.path.islink(f)],
                                     self.full_blacklist)
        self._pylint_full(sbin_list,
                          extra_args=["--module-rgx",
                                      "[a-z_-][a-z0-9_-]*$"])

    def _pylint_full(self, paths, extra_args=None):
        """ test select files for all pylint errors """
        if extra_args is None:
            extra_args = []
        args = self.pylint_cmd + extra_args + \
            [os.path.join(srcpath, p) for p in paths]
        pylint = Popen(args, stdout=PIPE, stderr=STDOUT)
        print(pylint.communicate()[0])
        self.assertEqual(pylint.wait(), 0)

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    @skipUnless(HAS_PYLINT, "pylint not found, skipping")
    def test_sbin_errors(self):
        all_sbin = [os.path.join(srcpath, "sbin", f)
                    for f in glob.glob(os.path.join(srcpath, "sbin", "*"))]
        sbin_list = blacklist_filter([f for f in all_sbin
                                      if not os.path.islink(f)],
                                     self.contingent_blacklist)
        self._pylint_errors(sbin_list,
                            extra_args=["--module-rgx",
                                        "[a-z_-][a-z0-9_-]*$"])

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    @skipUnless(HAS_PYLINT, "pylint not found, skipping")
    def test_contingent_errors(self):
        whitelist = expand_path_dict(error_checks)
        for (mods, filedict) in contingent_checks.items():
            if "django" in mods:
                # there's some issue with running pylint on modules
                # that use django in Travis CI (but not elsewhere), so
                # skip these for now
                continue
            try:
                for mod in mods:
                    __import__(mod)
            except ImportError:
                continue
            flist = \
                blacklist_filter(whitelist_filter(expand_path_dict(filedict),
                                                  whitelist),
                                     self.blacklist)
            self._pylint_errors(flist)

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    @skipUnless(HAS_PYLINT, "pylint not found, skipping")
    def test_lib_errors(self):
        filelist = blacklist_filter(expand_path_dict(error_checks),
                                    self.contingent_blacklist)
        return self._pylint_errors(filelist)

    def _pylint_errors(self, paths, extra_args=None):
        """ test all files for fatals and errors """
        if extra_args is None:
            extra_args = []
        args = self.pylint_cmd + extra_args + \
            ["-f", "parseable", "-d", "R0801,E1103"] + \
            [os.path.join(srcpath, p) for p in paths]
        pylint = Popen(args, stdout=PIPE, stderr=STDOUT)
        output = pylint.communicate()[0]
        rv = pylint.wait()

        for line in output.splitlines():
            if self.error_re.search(str(line)):
                print(line)
        # pylint returns a bitmask, where 1 means fatal errors
        # were encountered and 2 means errors were encountered.
        self.assertEqual(rv & 3, 0)
