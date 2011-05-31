#!/usr/bin/env python

"""
First attempt to make our export script more portable than export.sh
"""

import fileinput
from subprocess import Popen, PIPE
import sys

# Compatibility import
from Bcfg2.Bcfg2Py3k import formatdate

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
for line in fileinput.input('solaris/pkginfo.bcfg2', inplace=1):
    if line.startswith('VERSION='):
        line = line.replace(line, 'VERSION="%s"\n' % version)
    sys.stdout.write(line)
for line in fileinput.input('solaris/pkginfo.bcfg2-server', inplace=1):
    if line.startswith('VERSION='):
        line = line.replace(line, 'VERSION="%s"\n' % version)
    sys.stdout.write(line)
# update the version in reports
for line in fileinput.input('src/lib/Server/Reports/reports/templates/base.html',
                            inplace=1):
    if 'Bcfg2 Version' in line:
        line = line.replace(line, '    <span>Bcfg2 Version %s</span>\n' % version)
    sys.stdout.write(line)
# update the version in the docs
for line in fileinput.input('doc/conf.py', inplace=1):
    if line.startswith('version ='):
        line = line.replace(line, 'version = \'%s\'\n' % majorver[0:3])
    if line.startswith('release ='):
        line = line.replace(line, 'release = \'%s\'\n' % (majorver + minorver))
    sys.stdout.write(line)

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
