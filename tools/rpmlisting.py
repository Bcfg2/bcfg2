#!/usr/bin/python -u

import os
import sys
import subprocess
import getopt
import re
import datetime
from socket import gethostname


def run_or_die(command):
    """run a command, returning output.  raise an exception if it fails."""
    (status, stdio) = subprocess.getstatusoutput(command)
    if status != 0:
        raise Exception("command '%s' failed with exit status %d and output '%s'" %
                        (command, status, stdio))
    return stdio


def rpmblob_cmp(a, b):
    """cmp() implementation for rpmblobs, suitable for use with sort()."""
    ret = cmp(a['name'], b['name'])
    if ret == 0:
        ret = verstr_cmp(a['version'], b['version'])
        if ret == 0:
            ret = verstr_cmp(a['release'], b['release'])
    return ret


def verstr_cmp(a, b):
    """cmp() implementation for version strings, suitable for use with sort()."""
    ret = 0
    index = 0
    a_parts = subdivide(a)
    b_parts = subdivide(b)
    prerelease_pattern = re.compile('rc|pre')
    while ret == 0 and index < min(len(a_parts), len(b_parts)):
        subindex = 0
        a_subparts = a_parts[index]
        b_subparts = b_parts[index]
        while ret == 0 and subindex < min(len(a_subparts), len(b_subparts)):
            ret = cmp(a_subparts[subindex], b_subparts[subindex])
            if ret != 0:
                return ret
            subindex = subindex + 1
        if len(a_subparts) != len(b_subparts):
            # handle prerelease special case at subpart level (ie, '4.0.2rc5').
            if len(a_subparts) > len(b_subparts) and prerelease_pattern.match(str(a_subparts[subindex])):
                return -1
            elif len(a_subparts) < len(b_subparts) and prerelease_pattern.match(str(b_subparts[subindex])):
                return 1
            else:
                return len(a_subparts) - len(b_subparts)
        index = index + 1
    if len(a_parts) != len(b_parts):
        # handle prerelease special case at part level (ie, '4.0.2.rc5).
        if len(a_parts) > len(b_parts) and prerelease_pattern.match(str(a_parts[index][0])):
            return -1
        elif len(a_parts) < len(b_parts) and prerelease_pattern.match(str(b_parts[index][0])):
            return 1
        else:
            return len(a_parts) - len(b_parts)
    return ret


def subdivide(verstr):
    """subdivide takes a version or release string and attempts to subdivide
    it into components to facilitate sorting.  The string is divided into a
    two level hierarchy of sub-parts.  The upper level is subdivided by
    periods, and the lower level is subdivided by boundaries between digit,
    alpha, and other character groupings.
    """
    parts = []
    # parts is a list of lists representing the subsections which make up a version string.
    # example:
    # 4.0.2b3 would be represented as [[4],[0],[2,'b',3]].
    major_parts = verstr.split('.')
    for major_part in major_parts:
        minor_parts = []
        index = 0
        while index < len(major_part):
            # handle digit subsection
            if major_part[index].isdigit():
                digit_str_part = ""
                while index < len(major_part) and major_part[index].isdigit():
                    digit_str_part = digit_str_part + major_part[index]
                    index = index + 1
                digit_part = int(digit_str_part)
                minor_parts.append(digit_part)
            # handle alpha subsection
            elif major_part[index].isalpha():
                alpha_part = ""
                while index < len(major_part) and major_part[index].isalpha():
                    alpha_part = alpha_part + major_part[index]
                    index = index + 1
                minor_parts.append(alpha_part)
            # handle other characters.  this should only be '_', but we will treat is as a subsection to keep it general.
            elif not major_part[index].isalnum():
                other_part = ""
                while index < len(major_part) and not major_part[index].isalnum():
                    other_part = other_part + major_part[index]
                    index = index + 1
                minor_parts.append(other_part)
            parts.append(minor_parts)
    return parts


subarch_mapping = {'athlon': 'x86',
                   'i686': 'x86',
                   'i586': 'x86',
                   'i486': 'x86',
                   'i386': 'x86',
                   'x86_64': 'x86_64',
                   'noarch': 'noarch'}
arch_mapping = {'x86': ['athlon',
                        'i686',
                        'i586',
                        'i486',
                        'i386'],
                'x86_64': ['x86_64'],
                'noarch': ['noarch']}


def parse_rpm(path, filename):
    """read the name, version, release, and subarch of an rpm.
    this version reads the rpm headers.
    """
    cmd = 'rpm --nosignature --queryformat \'%%{NAME} %%{VERSION} %%{RELEASE} %%{ARCH}\' -q -p %s/%s' % (path, filename)
    output = run_or_die(cmd)
    (name, version, release, subarch) = output.split()
    if subarch not in list(subarch_mapping.keys()):
        raise Exception("%s/%s has invalid subarch %s" % (path, filename, subarch))
    return (name, version, release, subarch)


def parse_rpm_filename(path, filename):
    """read the name, version, release, and subarch of an rpm.
    this version tries to parse the filename directly, and calls
    'parse_rpm' as a fallback.
    """
    name, version, release, subarch = None, None, None, None
    try:
        (major, minor) = sys.version_info[:2]
        if major >= 2 and minor >= 4:
            (blob, subarch, extension) = filename.rsplit('.', 2)
            (name, version, release) = blob.rsplit('-', 2)
        else:
            (rextension, rsubarch, rblob) = filename[::-1].split('.', 2)
            (blob, subarch, extension) = (rblob[::-1], rsubarch[::-1], rextension[::-1])
            (rrelease, rversion, rname) = blob[::-1].split('-', 2)
            (name, version, release) = (rname[::-1], rversion[::-1], rrelease[::-1])
        if subarch not in list(subarch_mapping.keys()):
            raise "%s/%s has invalid subarch %s." % (path, filename, subarch)
    except:
        # for incorrectly named rpms (ie, sun's java rpms) we fall back to reading the rpm headers.
        sys.stderr.write("Warning: could not parse filename %s/%s.  Attempting to parse rpm headers.\n" % (path, filename))
        (name, version, release, subarch) = parse_rpm(path, filename)
    return (name, version, release, subarch)


def get_pkgs(rpmdir):
    """scan a dir of rpms and generate a pkgs structure. first try parsing
    the filename. if that fails, try parsing the rpm headers.
    """
    pkgs = {}
    """
pkgs structure:
* pkgs is a dict of package name, rpmblob list pairs:
  pkgs = {name:[rpmblob,rpmblob...], name:[rpmblob,rpmblob...]}
* rpmblob is a dict describing an rpm file:
  rpmblob = {'file':'foo-0.1-5.i386.rpm', 'name':'foo', 'version':'0.1', 'release':'5', 'subarch':'i386'},

example:
pkgs = {
'foo' : [
  {'file':'foo-0.1-5.i386.rpm', 'name':'foo', 'version':'0.1', 'release':'5', 'subarch':'i386'},
  {'file':'foo-0.2-3.i386.rpm', 'name':'foo', 'version':'0.2', 'release':'3', 'subarch':'i386'}],
'bar' : [
  {'file':'bar-3.2a-12.mips.rpm', 'name':'bar', 'version':'3.2a', 'release':'12', 'subarch':'mips'},
  {'file':'bar-3.7j-4.mips.rpm', 'name':'bar', 'version':'3.7j', 'release':'4', 'subarch':'mips'}]
}
"""
    rpms = [item for item in os.listdir(rpmdir) if item.endswith('.rpm')]
    for filename in rpms:
        (name, version, release, subarch) = parse_rpm_filename(rpmdir, filename)
        rpmblob = {'file': filename,
                   'name': name,
                   'version': version,
                   'release': release,
                   'subarch': subarch}
        if name in pkgs:
            pkgs[name].append(rpmblob)
        else:
            pkgs[name] = [rpmblob]
    return pkgs


def prune_pkgs_latest(pkgs):
    """prune a pkgs structure to contain only the latest version
    of each package (includes multiarch results).
    """
    latest_pkgs = {}
    for rpmblobs in list(pkgs.values()):
        (major, minor) = sys.version_info[:2]
        if major >= 2 and minor >= 4:
            rpmblobs.sort(rpmblob_cmp, reverse=True)
        else:
            rpmblobs.sort(rpmblob_cmp)
            rpmblobs.reverse()
        pkg_name = rpmblobs[0]['name']
        all_archs = [blob for blob in rpmblobs if blob['version'] == rpmblobs[0]['version'] and
                                                  blob['release'] == rpmblobs[0]['release']]
        latest_pkgs[pkg_name] = all_archs
    return latest_pkgs


def prune_pkgs_archs(pkgs):
    """prune a pkgs structure to contain no more than one subarch
    per architecture for each set of packages.
    """
    pruned_pkgs = {}
    for rpmblobs in list(pkgs.values()):
        pkg_name = rpmblobs[0]['name']
        arch_sifter = {}
        for challenger in rpmblobs:
            arch = subarch_mapping[challenger['subarch']]
            incumbent = arch_sifter.get(arch)
            if incumbent == None:
                arch_sifter[arch] = challenger
            else:
                subarchs = arch_mapping[arch]
                challenger_index = subarchs.index(challenger['subarch'])
                incumbent_index = subarchs.index(incumbent['subarch'])
                if challenger_index < incumbent_index:
                    arch_sifter[arch] = challenger
        pruned_pkgs[pkg_name] = list(arch_sifter.values())
    return pruned_pkgs


def get_date_from_desc(date_desc):
    """calls the unix 'date' command to turn a date
    description into a python date object.

    example: get_date_from_desc("last sunday 1 week ago")
    """
    stdio = run_or_die('date -d "' + date_desc + '" "+%Y %m %d"')
    (year_str, month_str, day_str) = stdio.split()
    year = int(year_str)
    month = int(month_str)
    day = int(day_str)
    date_obj = datetime.date(year, month, day)
    return date_obj


def get_mtime_date(path):
    """return a naive date object based on the file's mtime."""
    return datetime.date.fromtimestamp(os.stat(path).st_mtime)


def prune_pkgs_timely(pkgs, start_date_desc=None, end_date_desc=None, rpmdir='.'):
    """prune a pkgs structure to contain only rpms with
    an mtime within a certain temporal window.
    """
    start_date = None
    if start_date_desc != None:
        start_date = get_date_from_desc(start_date_desc)
    end_date = None
    if end_date_desc != None:
        end_date = get_date_from_desc(end_date_desc)
    if start_date == None and end_date == None:
        return pkgs
    if start_date != None:
        for rpmblobs in list(pkgs.values()):
            pkg_name = rpmblobs[0]['name']
            timely_blobs = [blob for blob in rpmblobs if start_date < get_mtime_date(rpmdir + '/' + blob['file'])]
            if len(timely_blobs) == 0:
                del pkgs[pkg_name]
            else:
                pkgs[pkg_name] = timely_blobs
    if end_date != None:
        for rpmblobs in list(pkgs.values()):
            pkg_name = rpmblobs[0]['name']
            timely_blobs = [blob for blob in rpmblobs if get_mtime_date(rpmdir + '/' + blob['file']) <= end_date]
            if len(timely_blobs) == 0:
                del pkgs[pkg_name]
            else:
                pkgs[pkg_name] = timely_blobs
    return pkgs


# from http://aspn.activestate.com/ASPN/Python/Cookbook/Recipe/52306
def sorted_values(adict):
    """return a list of values from a dict, sorted by key."""
    items = list(adict.items())
    items.sort()
    return [value for key, value in items]


def scan_rpm_dir(rpmdir, uri, group, priority=0, output=sys.stdout, start_date_desc=None, end_date_desc=None):
    """the meat of this library."""
    output.write('<PackageList uri="%s" type="yum" priority="%s">\n' % (uri, priority))
    output.write(' <Group name="%s">\n' % group)
    pkgs = prune_pkgs_archs(prune_pkgs_latest(prune_pkgs_timely(get_pkgs(rpmdir), start_date_desc, end_date_desc, rpmdir)))
    for rpmblobs in sorted_values(pkgs):
        if len(rpmblobs) == 1:
            # regular pkgmgr entry
            rpmblob = rpmblobs[0]
            output.write('  <Package name="%s" simplefile="%s" version="%s-%s"/>\n' %
                         (rpmblob['name'], rpmblob['file'], rpmblob['version'], rpmblob['release']))
        else:
            # multiarch pkgmgr entry
            rpmblob = rpmblobs[0]
            subarchs = [blob['subarch'] for blob in rpmblobs]
            subarchs.sort()
            multiarch_string = ' '.join(subarchs)
            pattern_string = '\.(%s)\.rpm$' % '|'.join(subarchs)  # e.g., '\.(i386|x86_64)\.rpm$'
            pattern = re.compile(pattern_string)
            multiarch_file = pattern.sub('.%(arch)s.rpm', rpmblob['file'])  # e.g., 'foo-1.0-1.%(arch)s.rpm'
            output.write('  <Package name="%s" file="%s" version="%s-%s" multiarch="%s"/>\n' %
                         (rpmblob['name'], multiarch_file, rpmblob['version'], rpmblob['release'], multiarch_string))
    output.write(' </Group>\n')
    output.write('</PackageList>\n')


def usage(output=sys.stdout):
    output.write("Usage: %s [-g <groupname>] [-u <uri>] [-d <dir>] [-p <priority>] [-o <output>]\n" % sys.argv[0])


if __name__ == "__main__":
    try:
        opts, args = getopt.getopt(sys.argv[1:], "g:u:d:p:o:",
                                   ["group=", "uir=", "dir=", "priority=", "output="])
    except getopt.GetoptError:
        usage(sys.stderr)
        sys.exit(1)

    group = "base"
    uri = "http://" + gethostname() + "/rpms"
    rpmdir = "."
    priority = "0"
    output = None

    for opt, arg in opts:
        if opt in ['-g', '--group']:
            group = arg
        elif opt in ['-u', '--uri']:
            uri = arg
        elif opt in ['-d', '--dir']:
            rpmdir = arg
        elif opt in ['-p', '--priority']:
            priority = arg
        elif opt in ['-o', '--output']:
            output = arg

    if output == None:
        output = sys.stdout
    else:
        output = file(output, "w")

    scan_rpm_dir(rpmdir, uri, group, priority, output)
