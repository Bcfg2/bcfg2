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
from common import can_skip, skip, skipIf, skipUnless, Bcfg2TestCase

try:
    import django
    HAS_DJANGO = True
except ImportError:
    HAS_DJANGO = False

# path to Bcfg2 src directory
srcpath = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                       "src"))
# we set this in the environment rather than with sys.path because we
# call pylint, an external command, later, and it needs the modified
# environment
if 'PYTHONPATH' in os.environ:
    os.environ['PYTHONPATH'] = os.environ['PYTHONPATH'] + ":" + \
        os.path.join(srcpath, "lib")
else:
    os.environ['PYTHONPATH'] = os.path.join(srcpath, "lib")

# path to pylint rc file
rcfile = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                      "pylintrc.conf"))

# test for pylint existence
try:
    Popen(['pylint'], stdout=PIPE, stderr=STDOUT).wait()
    HAS_PYLINT = True
except OSError:
    HAS_PYLINT = False


# perform a full range of code checks on the listed files.
full_checks = {
    "lib/Bcfg2": ["*.py"],
    "lib/Bcfg2/Server": ["Lint",
                         "Plugin",
                         "FileMonitor",
                         "*.py"],
    "lib/Bcfg2/Server/Plugins": ["Cfg", "Packages", "*.py"],
    "lib/Bcfg2/Client": ["*.py"],
    "lib/Bcfg2/Client/Tools": ["POSIX", "SELinux.py"],
    }

# perform full code checks on the listed executables
sbin_checks = {
    "sbin": ["bcfg2-server", "bcfg2-yum-helper", "bcfg2-crypt", "bcfg2-test",
             "bcfg2-lint"]
    }

# perform limited, django-safe checks on the listed files
django_checks = {
    "lib/Bcfg2/Server": ["Reports", "models.py"]
    }

# perform only error checking on the listed files
error_checks = {
    "lib/Bcfg2": ["Proxy.py", "SSLServer.py"],
    "lib/Bcfg2/Server/Plugins": ["Decisions.py",
                                 "Deps.py",
                                 "Ldap.py",
                                 "NagiosGen.py",
                                 "Pkgmgr.py",
                                 "SSHbase.py",
                                 "SSLCA.py"]
    }

# perform no checks at all on the listed files
no_checks = {
    "lib/Bcfg2/Client/Tools": ["APT.py", "RPMng.py", "rpmtools.py"],
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


def expand_path_dict(pathdict):
    """ given a path dict as above, return a list of all the paths """
    rv = []
    for parent, modules in pathdict.items():
        for mod in modules:
            rv.extend(glob.glob(os.path.join(srcpath, parent, mod)))
    return rv


class TestPylint(Bcfg2TestCase):
    pylint_cmd = ["pylint", "--rcfile", rcfile]

    # regex to find errors and fatal errors
    error_re = re.compile(r':\d+:\s+\[[EF]\d{4}')

    # build the blacklist
    blacklist = expand_path_dict(no_checks)

    def _get_paths(self, pathdict):
        return list(set(expand_path_dict(pathdict)) - set(self.blacklist))

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    @skipUnless(HAS_PYLINT, "pylint not found, skipping")
    def test_lib_full(self):
        full_list = list(set(self._get_paths(full_checks)) -
                         set(expand_path_dict(error_checks)))
        self._pylint_full(full_list)

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    @skipUnless(HAS_PYLINT, "pylint not found, skipping")
    def test_sbin_full(self):
        self._pylint_full(self._get_paths(sbin_checks),
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
        flist = list(set(os.path.join(srcpath, p)
                         for p in glob.glob("sbin/*")) - set(self.blacklist))
        return self._pylint_errors(flist)

    @skipUnless(HAS_DJANGO, "Django not found, skipping")
    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    @skipUnless(HAS_PYLINT, "pylint not found, skipping")
    def test_django_errors(self):
        return self._pylint_errors(self._get_paths(django_checks),
                                   extra_args=["-d", "E1101"])

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    @skipUnless(HAS_PYLINT, "pylint not found, skipping")
    def test_lib_errors(self):
        ignore = []
        for fname_list in django_checks.values() + no_checks.values():
            ignore.extend(fname_list)
        return self._pylint_errors(["lib/Bcfg2"],
                                   extra_args=["--ignore", ",".join(ignore)])

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
            #print line
            if self.error_re.search(line):
                print(line)
        # pylint returns a bitmask, where 1 means fatal errors
        # were encountered and 2 means errors were encountered.
        self.assertEqual(rv & 3, 0)
