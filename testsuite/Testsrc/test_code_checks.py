import os
import re
import sys
import glob
import copy
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

# path to base testsuite directory
testdir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# path to Bcfg2 src directory
srcpath = os.path.abspath(os.path.join(testdir, "..", "src"))

# path to pylint rc file
rcfile = os.path.join(testdir, "pylintrc.conf")

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
    ("apt",): {"lib/Bcfg2/Client/Tools": ["APT.py"]},
    ("yum",): {"lib/Bcfg2/Client/Tools": ["YUM.py"]},
    ("genshi",): {"lib/Bcfg2/Server/Plugins/Cfg": ["CfgGenshiGenerator.py"]},
    ("Cheetah",): {"lib/Bcfg2/Server/Plugins/Cfg": ["CfgCheetahGenerator.py"]},
    ("jinja2",): {"lib/Bcfg2/Server/Plugins/Cfg": ["CfgJinja2Generator.py"]},
    ("M2Crypto",): {"lib/Bcfg2": ["Encryption.py"],
                    "lib/Bcfg2/Server/Plugins/Cfg":
                        ["CfgEncryptedGenerator.py"]},
    ("M2Crypto", "genshi"): {"lib/Bcfg2/Server/Plugins/Cfg":
                                 ["CfgEncryptedGenshiGenerator.py"]},
    ("M2Crypto", "Cheetah"): {"lib/Bcfg2/Server/Plugins/Cfg":
                                  ["CfgEncryptedCheetahGenerator.py"]},
    ("M2Crypto", "jinja2"): {"lib/Bcfg2/Server/Plugins/Cfg":
                                  ["CfgEncryptedJinja2Generator.py"]},
    ("mercurial",): {"lib/Bcfg2/Server/Plugins": ["Hg.py"]},
    ("guppy",): {"lib/Bcfg2/Server/Plugins": ["Guppy.py"]},
    ("boto",): {"lib/Bcfg2/Server/Plugins": ["AWSTags.py"]},
}

# perform only error checking on the listed files
error_checks = {
    "lib/Bcfg2": ["Reporting"],
    "lib/Bcfg2/Client": ["Proxy.py"],
    "lib/Bcfg2/Server": ["Reports", "SchemaUpdater", "SSLServer.py"],
    "lib/Bcfg2/Server/Admin": ["Compare.py"],
    "lib/Bcfg2/Client/Tools": ["OpenCSW.py",
                               "Blast.py",
                               "FreeBSDInit.py",
                               "VCS.py",
                               "YUM24.py"],
    "lib/Bcfg2/Server/Plugins": ["Deps.py",
                                 "Pkgmgr.py"]
    }

# perform no checks at all on the listed files
no_checks = {
    "lib/Bcfg2/Client/Tools": ["RPM.py", "rpmtools.py"],
    "lib/Bcfg2/Server": ["Snapshots", "Hostbase"],
    "lib/Bcfg2": ["manage.py"],
    "lib/Bcfg2/Server/Reports": ["manage.py"],
    "lib/Bcfg2/Server/Plugins": ["Base.py"],
    "lib/Bcfg2/Server/migrations": ["*.py"],
    "lib/Bcfg2/Server/south_migrations": ["*.py"],
    }
if sys.version_info < (2, 6):
    # multiprocessing core requires py2.6
    no_checks['lib/Bcfg2/Server'] = ['MultiprocessingCore.py']

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


class CodeTestCase(Bcfg2TestCase):
    __test__ = False

    # build the blacklists
    blacklist = expand_path_dict(no_checks)

    contingent_blacklist = []
    for filedict in contingent_checks.values():
        contingent_blacklist += expand_path_dict(filedict)

    full_blacklist = expand_path_dict(error_checks) + contingent_blacklist + \
        blacklist

    command = [None]

    has_command = None

    # extra arguments when running tests on sbin/*
    sbin_args = []

    # extra arguments when running tests on lib/*
    lib_args = []

    # extra arguments for full tests
    full_args = []

    # extra arguments for error tests
    error_args = []

    def has_exec(self):
        if self.has_command is None:
            try:
                Popen(self.command,
                      stdin=PIPE, stdout=PIPE, stderr=STDOUT).wait()
                self.has_command = True
            except OSError:
                self.has_command = False
        return self.has_command

    def get_env(self):
        if ('PYTHONPATH' not in os.environ or
            testdir not in os.environ['PYTHONPATH'].split(":")):
            env = copy.copy(os.environ)
            env['PYTHONPATH'] = ':'.join([env.get("PYTHONPATH", ""),
                                          testdir])
            return env
        else:
            return os.environ

    def _test_full(self, files, extra_args=None):
        """ test select files for all problems """
        if not len(files):
            return
        if extra_args is None:
            extra_args = []
        cmd = self.command + self.full_args + extra_args + \
            [os.path.join(srcpath, f) for f in files]
        proc = Popen(cmd, stdout=PIPE, stderr=STDOUT, env=self.get_env())
        print(proc.communicate()[0].decode())
        self.assertEqual(proc.wait(), 0)

    def _test_errors(self, files, extra_args=None):
        """ test select files for errors """
        if not len(files):
            return
        if extra_args is None:
            extra_args = []
        cmd = self.command + self.error_args + extra_args + \
            [os.path.join(srcpath, f) for f in files]
        proc = Popen(cmd, stdout=PIPE, stderr=STDOUT, env=self.get_env())
        print(proc.communicate()[0].decode())
        self.assertEqual(proc.wait(), 0)

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    def test_lib_full(self):
        @skipUnless(self.has_exec(),
                    "%s not found, skipping" % self.command[0])
        def inner():
            full_list = []
            for root, _, files in os.walk(os.path.join(srcpath, "lib")):
                full_list.extend(blacklist_filter([os.path.join(root, f)
                                                   for f in files
                                                   if f.endswith(".py")],
                                                  self.full_blacklist))
            self._test_full(full_list, extra_args=self.lib_args)

        inner()

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    def test_contingent_full(self):
        @skipUnless(self.has_exec(),
                    "%s not found, skipping" % self.command[0])
        def inner():
            filelist = []
            blacklist = set(expand_path_dict(error_checks) + self.blacklist)
            for (mods, filedict) in contingent_checks.items():
                try:
                    for mod in mods:
                        __import__(mod)
                except ImportError:
                    continue
                filelist.extend(expand_path_dict(filedict))
            self._test_full(blacklist_filter(filelist, blacklist),
                            extra_args=self.lib_args)

        inner()

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    def test_sbin(self):
        @skipUnless(self.has_exec(),
                    "%s not found, skipping" % self.command[0])
        def inner():
            all_sbin = [os.path.join(srcpath, "sbin", f)
                        for f in glob.glob(os.path.join(srcpath, "sbin", "*"))]
            full_list = blacklist_filter([f for f in all_sbin
                                          if not os.path.islink(f)],
                                         self.full_blacklist)
            self._test_full(full_list, extra_args=self.sbin_args)

            errors_list = blacklist_filter([f for f in all_sbin
                                            if not os.path.islink(f)],
                                           self.contingent_blacklist)
            self._test_errors(errors_list, extra_args=self.sbin_args)

        inner()

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    def test_contingent_errors(self):
        @skipUnless(self.has_exec(),
                    "%s not found, skipping" % self.command[0])
        def inner():
            filelist = []
            whitelist = expand_path_dict(error_checks)
            for (mods, filedict) in contingent_checks.items():
                try:
                    for mod in mods:
                        __import__(mod)
                except ImportError:
                    continue
                filelist.extend(expand_path_dict(filedict))
            flist = blacklist_filter(whitelist_filter(filelist, whitelist),
                                     self.blacklist)
            self._test_errors(flist, extra_args=self.lib_args)

        inner()

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    def test_lib_errors(self):
        @skipUnless(self.has_exec(),
                    "%s not found, skipping" % self.command[0])
        def inner():
            filelist = blacklist_filter(expand_path_dict(error_checks),
                                        self.contingent_blacklist)
            return self._test_errors(filelist, extra_args=self.lib_args)

        inner()


class TestPylint(CodeTestCase):
    __test__ = True
    command = ["pylint", "--rcfile", rcfile, "--init-hook",
               "import sys;sys.path.append('%s')" %
               os.path.join(srcpath, "lib")]

    sbin_args = ["--module-rgx", "[a-z_-][a-z0-9_-]*$"]
    error_args = ["-f", "parseable", "-d", "R0801,E1103"]

    # regex to find errors and fatal errors
    error_re = re.compile(r':\d+:\s+\[[EF]\d{4}')

    def __init__(self, *args, **kwargs):
        CodeTestCase.__init__(self, *args, **kwargs)
        for mods, filedict in contingent_checks.items():
            if "django" in mods:
                # there's some issue with running pylint on modules
                # that use django in Travis CI (but not elsewhere), so
                # skip these for now
                self.blacklist += expand_path_dict(filedict)

    def _test_errors(self, files, extra_args=None):
        """ test all files for fatals and errors """
        if not len(files):
            return
        if extra_args is None:
            extra_args = []
        args = self.command + self.error_args + extra_args + \
            [os.path.join(srcpath, p) for p in files]
        pylint = Popen(args, stdout=PIPE, stderr=STDOUT, env=self.get_env())
        output = pylint.communicate()[0].decode()
        rv = pylint.wait()

        for line in output.splitlines():
            if self.error_re.search(str(line)):
                print(line)
        # pylint returns a bitmask, where 1 means fatal errors
        # were encountered and 2 means errors were encountered.
        self.assertEqual(rv & 3, 0)


class TestPEP8(CodeTestCase):
    __test__ = True
    command = ["pep8", "--ignore=E125,E129,E501"]

    def _test_errors(self, files, extra_args=None):
        pass
