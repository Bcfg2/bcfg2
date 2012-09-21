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

# path to pylint rc file
rcfile = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                      "pylintrc.conf"))


class TestPylint(Bcfg2TestCase):
    # right now, too many things fail pylint miserably to just test
    # everything, or even to do a blacklist, so we just whitelist the
    # things we do want to do a full check on and only check most
    # stuff for errors and fatal errors.  This is a dict of
    # <directory> => <file globs within that directory>.  <directory>
    # is relative to src/
    whitelist = {
        "lib/Bcfg2/Server": ["Plugin"],
        "lib/Bcfg2/Server/Plugins": ["PuppetENC.py",
                                     "Rules.py",
                                     "DBStats.py",
                                     "Trigger.py",
                                     "Defaults.py",
                                     "Probes.py",
                                     "TemplateHelper.py",
                                     "Guppy.py",
                                     "FileProbes.py",
                                     "ServiceCompat.py",
                                     "Properties.py",
                                     "SEModules.py",
                                     "Darcs.py",
                                     "Git.py",
                                     "Hg.py",
                                     "Cvs.py",
                                     "Fossil.py",
                                     "Svn.py",
                                     "Svn2.py",
                                     "Bzr.py",
                                     "Cfg",
                                     "Packages"]
        }

    pylint_cmd = ["pylint", "--rcfile", rcfile]

    # regex to find errors and fatal errors
    error_re = re.compile(r':\d+:\s+\[[EF]\d{4}')

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    def test_pylint_full(self):
        paths = []
        for parent, modules in self.whitelist.items():
            paths.extend([os.path.join(srcpath, parent, m) for m in modules])
        args = self.pylint_cmd + paths
        try:
            pylint = Popen(args, stdout=PIPE, stderr=STDOUT)
            print(pylint.communicate()[0])
            rv = pylint.wait()
        except OSError:
            if can_skip:
                return skip("pylint not found")
            else:
                print("pylint not found")
                return
        self.assertEqual(rv, 0)

    def test_sbin_errors(self):
        return self._pylint_errors(glob.glob("sbin/*"))

    @skipUnless(HAS_DJANGO, "Django not found, skipping")
    def test_django_errors(self):
        return self._pylint_errors(["lib/Bcfg2/Server/Reports",
                                    "lib/Bcfg2/Server/models.py"],
                                   extra_args=["-d", "E1101"])

    def test_lib_errors(self):
        # we ignore stuff that uses django (Reports, Hostbase,
        # models.py) or that is deprecated and raises lots of errors
        # (Snapshots, Hostbase), or that just raises a lot of errors
        # (APT.py, RPMng.py, rpmtools.py).  Reports is tested by
        # test_django_errors
        ignore = ["models.py", "APT.py", "RPMng.py", "rpmtools.py",
                  "Snapshots", "Reports", "Hostbase"]
        return self._pylint_errors(["lib/Bcfg2"],
                                   extra_args=["--ignore", ",".join(ignore)])

    @skipIf(not os.path.exists(srcpath), "%s does not exist" % srcpath)
    @skipIf(not os.path.exists(rcfile), "%s does not exist" % rcfile)
    def _pylint_errors(self, paths, extra_args=None):
        """ test all files for fatals and errors """
        if extra_args is None:
            extra_args = []
        args = self.pylint_cmd + extra_args + \
            ["-f", "parseable", "-d", "R0801,E1103"] + \
            [os.path.join(srcpath, p) for p in paths]
        try:
            pylint = Popen(args, stdout=PIPE, stderr=STDOUT)
            output = pylint.communicate()[0]
            rv = pylint.wait()
        except OSError:
            if can_skip:
                return skip("pylint not found")
            else:
                print("pylint not found")
                return

        for line in output.splitlines():
            #print line
            if self.error_re.search(line):
                print(line)
        # pylint returns a bitmask, where 1 means fatal errors
        # were encountered and 2 means errors were encountered.
        self.assertEqual(rv & 3, 0)
