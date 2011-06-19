#!/usr/bin/env python

"""
First attempt to make our export script more portable than export.sh
"""

import fileinput
from subprocess import Popen, PIPE
import sys

# py3k compatibility
try:
    from email.Utils import formatdate
except ImportError:
    from email.utils import formatdate

pkgname = 'bcfg2'
ftphost = 'terra.mcs.anl.gov'
ftpdir = '/mcs/ftp/pub/bcfg'
# py3k compatibility
try:
    version = raw_input("Please enter the version you are tagging (e.g. 1.0.0): ")
except NameError:
    version = input("Please enter the version you are tagging (e.g. 1.0.0): ")
tarname = '/tmp/%s-%s.tar.gz' % (pkgname, version)


def run(command):
    return Popen(command, shell=True, stdout=PIPE).communicate()

def find_and_replace(f, iftest, rline, startswith=False):
    for line in fileinput.input(f, inplace=1):
        if startswith:
            if line.startswith(iftest):
                line = line.replace(line, rline)
            sys.stdout.write(line)
        else:
            if iftest in line and line != "Version: %{version}\n":
                line = line.replace(line, rline)
            sys.stdout.write(line)

# update the version
majorver = version[:5]
minorver = version[5:]
# py3k compatibility
try:
    name = raw_input("Your name: ")
    email = raw_input("Your email: ")
except NameError:
    name = input("Your name: ")
    email = input("Your email: ")
newchangelog = \
"""bcfg2 (%s-0.0%s) unstable; urgency=low

  * New upstream release

 -- %s <%s>  %s

""" % (majorver, minorver, name, email, formatdate(localtime=True))
# write out the new debian changelog
with open('debian/changelog', 'r+') as f:
    old = f.read()
    f.seek(0)
    f.write(newchangelog + old)
f.close()
# Update redhat directory versions
with open('redhat/VERSION', 'w') as f:
    f.write("%s\n" % majorver)
f.close()
with open('redhat/RELEASE', 'w') as f:
    f.write("0.0%s\n" % minorver)
f.close()
# update solaris version
find_and_replace('solaris/Makefile', 'VERS=',
                 'VERS=%s-1\n' % version, startswith=True)
find_and_replace('solaris/pkginfo.bcfg2', 'VERSION=',
                 'VERSION="%s"\n' % version, startswith=True)
find_and_replace('solaris/pkginfo.bcfg2-server', 'VERSION=',
                 'VERSION="%s"\n' % version, startswith=True)
# set new version in setup.py
find_and_replace('setup.py', 'version=', '      version="%s",\n' % version)
# replace version in misc/bcfg2.spec
find_and_replace('misc/bcfg2.spec', 'Version:',
                 'Version:          %s\n' % version)
# update the version in reports
find_and_replace('src/lib/Server/Reports/reports/templates/base.html',
                 'Bcfg2 Version', '    <span>Bcfg2 Version %s</span>\n' % version)
# update the version in the docs
find_and_replace('doc/conf.py', 'version =',
                 'version = \'%s\'\n' % majorver[0:3], startswith=True)
find_and_replace('doc/conf.py', 'release =',
                 'release = \'%s\'\n' % (majorver + minorver), startswith=True)

# tag the release
#FIXME: do this using python-dulwich
cmd = "git commit -asm 'Version bump to %s'" % version
output = run(cmd)[0].strip()
# NOTE: This will use the default email address key. If you want to sign the tag
#       using a different key, you will need to set 'signingkey' to the proper
#       value in the [user] section of your git configuration.
cmd = "git tag -s v%s -m 'tagged %s release'" % (version, version)
output = run(cmd)[0].strip()
cmd = "git archive --format=tar --prefix=%s-%s/ v%s | gzip > %s" % \
       (pkgname, version, version, tarname)
output = run(cmd)[0].strip()
cmd = "gpg --armor --output %s.gpg --detach-sig  %s" % (tarname, tarname)
output = run(cmd)[0].strip()

# upload release to ftp
cmd = "scp %s* terra.mcs.anl.gov:/mcs/ftp/pub/bcfg/" % tarname
output = run(cmd)[0].strip()
