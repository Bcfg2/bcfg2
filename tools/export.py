#!/usr/bin/env python

"""
First attempt to make our export script more portable than export.sh
"""

from email.Utils import formatdate
import fileinput
from subprocess import Popen, PIPE
import sys

pkgname = 'bcfg2'
repo = 'https://svn.mcs.anl.gov/repos/bcfg'
version = raw_input("Please enter the version you are tagging (e.g. 1.0.0): ")
tagstr = version.replace('.', '_')

expath = "/tmp/%s-%s/" % (pkgname, version)
tarname = "/tmp/%s-%s.tar.gz" % (pkgname, version)

def run(command):
    return Popen(command, shell=True, stdout=PIPE).communicate()

#FIXME: someone please figure out how to do this using the python svn bindings
cmd = "svn info | grep URL | awk '{print $2}'"
url = run(cmd)[0].strip()

# update the version
majorver = version[:5]
minorver = version[5:]
name = raw_input("Your name: ")
email = raw_input("Your email: ")
newchangelog = \
"""bcfg2 (%s-0.0%s) unstable; urgency=low

  * New upstream release

 -- %s <%s> %s

""" % (majorver, minorver, name, email, formatdate(localtime=True))
# write out the new debian changelog
with open('debian/changelog', 'r+') as f:
    old = f.read()
    f.seek(0)
    f.write(newchangelog + old)
f.close()
# set new version in setup.py
for line in fileinput.input('setup.py', inplace=1):
    if 'version' in line:
        line = line.replace(line, '      version="%s",\n' % version)
    sys.stdout.write(line)
# replace version in misc/bcfg2.spec
for line in fileinput.input('misc/bcfg2.spec', inplace=1):
    if 'Version:' in line and line != "Version: %{version}\n":
        line = line.replace(line, 'Version:          %s\n' % version)
    sys.stdout.write(line)
# Update redhat directory versions
with open('redhat/VERSION', 'w') as f:
    f.write("%s\n" % majorver)
f.close()
with open('redhat/RELEASE', 'w') as f:
    f.write("0.0%s\n" % minorver)
f.close()
# update solaris version
for line in fileinput.input('solaris/Makefile', inplace=1):
    if line.startswith('VERS='):
        line = line.replace(line, 'VERS=%s-1\n' % version)
    sys.stdout.write(line)
# tag the release
cmd = "svn ci -m 'Version bump to %s'" % version
output = run(cmd)[0].strip()
cmd = "svn copy %s %s/tags/%s_%s -m 'tagged %s release'" % \
      (url, repo, pkgname, tagstr, version)
output = run(cmd)[0].strip()
cmd = "svn export %s" % expath
output = run(cmd)[0].strip()
cmd = "svn log -v %s/tags/%s_%s > %sChangelog" % \
      (repo, pkgname, tagstr, expath)
output = run(cmd)[0].strip()
cmd = "tar czf %s %s" % (tarname, expath)
output = run(cmd)[0].strip()
cmd = "gpg --armor --output %s.gpg --detach-sig  %s" % (tarname, tarname)
output = run(cmd)[0].strip()
cmd = "scp %s* terra.mcs.anl.gov:/mcs/ftp/pub/bcfg" % tarname
output = run(cmd)[0].strip()
