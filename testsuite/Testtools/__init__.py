import os
import re
import sys

# add all parent testsuite directories to sys.path to allow (most)
# relative imports in python 2.4
path = os.path.dirname(__file__)
while path != "/":
    if os.path.basename(path).lower().startswith("test"):
        sys.path.append(path)
    if os.path.basename(path) == "testsuite":
        break
    path = os.path.dirname(path)
from common import *

TOOLSDIR = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        "..", "..", "tools"))

class TestToolsDocs(Bcfg2TestCase):
    blankline = re.compile(r'^\s*$')

    @skipUnless(os.path.exists(TOOLSDIR),
                "%s does not exist, skipping tools/ tests" % TOOLSDIR)
    def tools_in_README(self, toolsdir=None):
        if toolsdir is None:
            toolsdir = TOOLSDIR
        script = None
        desc = None
        started = False
        rv = dict()
        for line in open(os.path.join(toolsdir, "README")).readlines():
            if not started:
                # skip up to the first blank line
                if self.blankline.match(line):
                    started = True
            elif not self.blankline.match(line):
                match = re.match(r'^(\S+)', line)
                if match:
                    script = match.group(1)
                    desc = ''
                else:
                    match = re.match(r'^\s+(?:-\s+)?(.*)$', line)
                    if match:
                        desc += match.group(1)
            else:
                # blank line
                if script and desc:
                    rv[script] = desc
        if script and desc:
            rv[script] = desc
        return rv

    @skipUnless(os.path.exists(TOOLSDIR),
                "%s does not exist, skipping tools/ tests" % TOOLSDIR)
    def test_all_scripts_in_README(self, prefix=''):
        toolsdir = os.path.join(TOOLSDIR, prefix)
        tools = self.tools_in_README(toolsdir=toolsdir)
        for fname in os.listdir(toolsdir):
            if fname == 'README':
                continue
            dname = os.path.join(prefix, fname) # display name
            fpath = os.path.join(toolsdir, fname)
            if os.path.isfile(fpath):
                self.assertIn(fname, tools,
                              msg="%s has no entry in README" % dname)
                self.assertNotRegexpMatches(tools[fname], r'^(\s|\?)*$',
                                    msg="%s has an empty entry in README" %
                                    dname)

    @skipUnless(os.path.exists(TOOLSDIR),
                "%s does not exist, skipping tools/ tests" % TOOLSDIR)
    def test_no_extras_in_README(self, prefix=''):
        toolsdir = os.path.join(TOOLSDIR, prefix)
        tools = self.tools_in_README(toolsdir=toolsdir)
        for fname in tools.keys():
            dname = os.path.join(prefix, fname) # display name
            fpath = os.path.join(toolsdir, fname)
            self.assertTrue(os.path.exists(fpath),
                            msg="%s is listed in README but does not exist" %
                            dname)

    @skipUnless(os.path.exists(TOOLSDIR),
                "%s does not exist, skipping tools/ tests" % TOOLSDIR)
    def test_upgrade_scripts_documented(self):
        upgrade = os.path.join(TOOLSDIR, "upgrade")
        for udir in os.listdir(upgrade):
            upath = os.path.join(upgrade, udir)
            dname = os.path.join("upgrade", udir) # display name
            self.assertTrue(os.path.isdir(upath),
                            msg="Unexpected script %s found in %s" % (udir,
                                                                      dname))
            self.assertTrue(os.path.exists(os.path.join(upath, 'README')),
                            msg="%s has no README" % dname)
            self.test_all_scripts_in_README(dname)

                
