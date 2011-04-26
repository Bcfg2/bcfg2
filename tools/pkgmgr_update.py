#!/usr/bin/python

"""
    Program to update an existing bcfg2 Pkgmgr configuration file from a list
    of directories that contain RPMS.

    Only the epoch, version, release and simplefiles attributes are updated
    in existing entries.  All other entries and attributes are preserved.

    This is a total hack until a proper more generalised system for managing
    Pkgmgr configuation files is developed.
"""

__version__ = '0.1'

import datetime
import glob
import gzip
import optparse
import os
import rpm
import sys

# Compatibility imports
from Bcfg2.Bcfg2Py3k import urljoin

try:
    from lxml.etree import parse, tostring
except:
    from elementtree.ElementTree import parse, tostring

installOnlyPkgs = ['kernel',
                   'kernel-bigmem',
                   'kernel-enterprise',
                   'kernel-smp',
                   'kernel-modules',
                   'kernel-debug',
                   'kernel-unsupported',
                   'kernel-source',
                   'kernel-devel',
                   'kernel-default',
                   'kernel-largesmp-devel',
                   'kernel-largesmp',
                   'kernel-xen',
                   'gpg-pubkey']


def readRpmHeader(ts, filename):
    """
        Read an rpm header from an RPM file.
    """
    try:
        fd = os.open(filename, os.O_RDONLY)
    except:
        print("Failed to open RPM file %s" % filename)

    h = ts.hdrFromFdno(fd)
    os.close(fd)
    return h


def sortedDictValues(adict):
    """
        Sort a dictionary by its keys and return the items in sorted key order.
    """
    keys = list(adict.keys())
    keys.sort()
    return list(map(adict.get, keys))


def cmpRpmHeader(a, b):
    """
        cmp() implemetation suitable for use with sort.
    """
    n1 = str(a.get('name'))
    e1 = str(a.get('epoch'))
    v1 = str(a.get('version'))
    r1 = str(a.get('release'))
    n2 = str(b.get('name'))
    e2 = str(b.get('epoch'))
    v2 = str(b.get('version'))
    r2 = str(b.get('release'))

    return rpm.labelCompare((e1, v1, r1), (e2, v2, r2))


def loadRpms(dirs):
    """
       dirs is a list of directories to search for rpms.

       Builds a multilevel dictionary keyed by the package name and arch.
       Arch dictionary item is a list, one entry per package instance found.

       The list entries are dictionaries.  Keys are 'filename', 'mtime' 'name',
       'arch', 'epoch', 'version' and 'release'.

       e.g.

       packages = {
       'bcfg2' : { 'noarch' : [ {'filename':'bcfg2-0.9.2-0.0rc1.noarch.rpm', 'mtime':'',
                                 'name':'bcfg2', 'arch':'noarch', 'epoch':None, 'version':'0.9.2',
                                 'release':'0.0rc1'}
                                {'filename':'bcfg2-0.9.2-0.0rc5.noarch.rpm', 'mtime':'',
                                 'name':'bcfg2', 'arch':'noarch', 'epoch':None, 'version':'0.9.2',
                                 'release':'0.0rc5'}]},
       'bcfg2-server' { 'noarch' : [ {'filename':'bcfg2-server-0.9.2-0.0rc1.noarch.rpm', 'mtime':'',
                                      'name':'bcfg2-server', 'arch':'noarch', 'epoch':None,
                                      'version':'0.9.2', 'release':'0.0rc1'}
                                     {'filename':'bcfg2-server-0.9.2-0.0rc5.noarch.rpm', 'mtime':'',
                                      'name':"bcfg2-server', 'arch':'noarch', 'epoch':None,
                                      'version':'0.9.2', 'release':'0.0rc5'}]},
       }
    """
    packages = {}
    ts = rpm.TransactionSet()
    vsflags = 0
    vsflags |= rpm._RPMVSF_NODIGESTS
    vsflags |= rpm._RPMVSF_NOSIGNATURES
    ovsflags = ts.setVSFlags(vsflags)
    for dir in dirs:

        if options.verbose:
            print("Scanning directory: %s" % dir)

        for file in [files for files in os.listdir(dir)
                           if files.endswith('.rpm')]:

            filename = os.path.join(dir, file)

            # Get the mtime of the RPM file.
            file_mtime = datetime.date.fromtimestamp(os.stat(filename).st_mtime)

            # Get the RPM header
            header = readRpmHeader(ts, filename)

            # Get what we are interesting in out of the header.
            name = header[rpm.RPMTAG_NAME]
            epoch = header[rpm.RPMTAG_EPOCH]
            version = header[rpm.RPMTAG_VERSION]
            release = header[rpm.RPMTAG_RELEASE]
            subarch = header[rpm.RPMTAG_ARCH]

            if name not in installOnlyPkgs:
                packages.setdefault(name, {}).setdefault(subarch, []).append({'filename': file,
                                                                              'mtime': file_mtime,
                                                                              'name': name,
                                                                              'arch': subarch,
                                                                              'epoch': epoch,
                                                                              'version': version,
                                                                              'release': release})
            if options.verbose:
                sys.stdout.write('.')
                sys.stdout.flush()
        if options.verbose:
            sys.stdout.write('\n')

    return packages


class pkgmgr_URLopener(urllib.FancyURLopener):
    """
        Override default error handling so that we can see what the errors are.
    """
    def http_error_default(self, url, fp, errcode, errmsg, headers):
        """
            Override default error handling so that we can see what the errors are.
        """
        print("ERROR %s: Unable to retrieve %s" % (errcode, url))


def loadRepos(repolist):
    """
       repolist is a list of urls to yum repositories.

       Builds a multilevel dictionary keyed by the package name and arch.
       Arch dictionary item is a list, one entry per package instance found.

       The list entries are dictionaries.  Keys are 'filename', 'mtime' 'name',
       'arch', 'epoch', 'version' and 'release'.

       e.g.

       packages = {
       'bcfg2' : { 'noarch' : [ {'filename':'bcfg2-0.9.2-0.0rc1.noarch.rpm', 'mtime':'',
                                 'name':'bcfg2', 'arch':'noarch', 'epoch':None, 'version':'0.9.2',
                                 'release':'0.0rc1'}
                                {'filename':'bcfg2-0.9.2-0.0rc5.noarch.rpm', 'mtime':'',
                                 'name':'bcfg2', 'arch':'noarch', 'epoch':None, 'version':'0.9.2',
                                 'release':'0.0rc5'}]},
       'bcfg2-server' { 'noarch' : [ {'filename':'bcfg2-server-0.9.2-0.0rc1.noarch.rpm', 'mtime':'',
                                      'name':'bcfg2-server', 'arch':'noarch', 'epoch':None,
                                      'version':'0.9.2', 'release':'0.0rc1'}
                                     {'filename':'bcfg2-server-0.9.2-0.0rc5.noarch.rpm', 'mtime':'',
                                      'name':"bcfg2-server', 'arch':'noarch', 'epoch':None,
                                      'version':'0.9.2', 'release':'0.0rc5'}]},
       }

    """
    packages = {}
    for repo in repolist:
        url = urljoin(repo, './repodata/repomd.xml')

        try:
            opener = pkgmgr_URLopener()
            file, message = opener.retrieve(url)
        except:
            sys.exit()

        try:
            tree = parse(file)
        except IOError:
            print("ERROR: Unable to parse retrieved repomd.xml.")
            sys.exit()

        repomd = tree.getroot()
        for element in repomd:
            if element.tag.endswith('data') and element.attrib['type'] == 'primary':
                for property in element:
                    if property.tag.endswith('location'):
                        primaryhref = property.attrib['href']

        url = urljoin(repo, './' + primaryhref)

        if options.verbose:
            print("Loading : %s" % url)

        try:
            opener = pkgmgr_URLopener()
            file, message = opener.retrieve(url)
        except:
            sys.exit()

        try:
            repo_file = gzip.open(file)
            tree = parse(repo_file)
        except IOError:
            print("ERROR: Unable to parse retrieved file.")
            sys.exit()

        root = tree.getroot()
        for element in root:
            if element.tag.endswith('package'):
                for property in element:
                    if property.tag.endswith('name'):
                        name = property.text
                    elif property.tag.endswith('arch'):
                        subarch = property.text
                    elif property.tag.endswith('version'):
                        version = property.get('ver')
                        epoch = property.get('epoch')
                        release = property.get('rel')
                    elif property.tag.endswith('location'):
                        file = property.get('href')

                if name not in installOnlyPkgs:
                    packages.setdefault(name, {}).setdefault(subarch, []).append({'filename': file,
                                                                                  'name': name,
                                                                                  'arch': subarch,
                                                                                  'epoch': epoch,
                                                                                  'version': version,
                                                                                  'release': release})
                if options.verbose:
                    sys.stdout.write('.')
                    sys.stdout.flush()
        if options.verbose:
            sys.stdout.write('\n')

    return packages


def str_evra(instance):
    """
        Convert evra dict entries to a string.
    """
    if instance.get('epoch', '*') == '*' or instance.get('epoch', '*') == None:
        return '%s-%s.%s' % (instance.get('version', '*'), instance.get('release', '*'),
                             instance.get('arch', '*'))
    else:
        return '%s:%s-%s.%s' % (instance.get('epoch', '*'), instance.get('version', '*'),
                                instance.get('release', '*'), instance.get('arch', '*'))


def updatepkg(pkg):
    """
    """
    global package_dict
    name = pkg.get('name')
    if name not in installOnlyPkgs:
        for inst in [inst for inst in pkg if inst.tag == 'Instance']:
            arch = inst.get('arch')
            if name in package_dict:
                if arch in package_dict[name]:
                    package_dict[name][arch].sort(cmpRpmHeader)
                    latest = package_dict[name][arch][-1]
                    if cmpRpmHeader(inst, latest) == -1:
                        if options.verbose:
                            print("Found newer version of package %s" % name)
                            print("    Updating %s to %s" % (str_evra(inst),
                                                             str_evra(latest)))
                        if latest['epoch'] != None:
                            inst.attrib['epoch'] = str(latest['epoch'])
                        inst.attrib['version'] = latest['version']
                        inst.attrib['release'] = latest['release']
                        if inst.get('simplefile', False):
                            inst.attrib['simplefile'] = latest['filename']
                        if options.altconfigfile:
                            ignoretags = pkg.xpath(".//Ignore")
                            # if we find Ignore tags, then assume they're correct;
                            # otherwise, check the altconfigfile
                            if not ignoretags:
                                altpkgs = alttree.xpath(".//Package[@name='%s'][Ignore]" % name)
                                if (len(altpkgs) == 1):
                                    for ignoretag in altpkgs[0].xpath(".//Ignore"):
                                        if options.verbose:
                                            print("    Found Ignore tag in altconfigfile for package %s" % name)
                                        pkg.append(ignoretag)


def main():
    global package_dict
    global alttree
    if options.verbose:
        print("Loading Pkgmgr config file %s." % (options.configfile))

    tree = parse(options.configfile)
    config = tree.getroot()

    if options.altconfigfile:
        if options.verbose:
            print("Loading Pkgmgr alternate config file %s." %
                  (options.altconfigfile))

        alttree = parse(options.altconfigfile)

    if options.verbose:
        print("Loading package headers")

    if options.rpmdirs:
        package_dict = loadRpms(search_dirs)
    elif options.yumrepos:
        package_dict = loadRepos(repos)

    if options.verbose:
        print("Processing package headers")

    for pkg in config.getiterator('Package'):
        updatepkg(pkg)

    output.write(tostring(config))

if __name__ == "__main__":

    p = optparse.OptionParser()

    p.add_option('--configfile', '-c', action='store', \
                                   type='string', \
                                   help='Existing Pkgmgr configuration  file name.')
    p.add_option('--altconfigfile', '-a', action='store', \
                                   type='string', \
                                   help='''Alternate, existing Pkgmgr configuration file name to read
                                           Ignore tags from (used for upgrades).''')

    p.add_option('--rpmdirs', '-d', action='store',
                                   type='string', \
                                   help='''Comma separated list of directories to scan for RPMS.
                                           Wilcards are permitted.''')

    p.add_option('--outfile', '-o', action='store', \
                                   type='string', \
                                   help='Output file name or new Pkgrmgr file.')

    p.add_option('--verbose', '-v', action='store_true', \
                                    help='Enable verbose output.')

    p.add_option('--yumrepos', '-y', action='store',
                                   type='string', \
                                   help='''Comma separated list of YUM repository URLs to load.
                                           NOTE: Each URL must end in a '/' character.''')
    options, arguments = p.parse_args()

    if not options.configfile:
        print("An existing Pkgmgr configuration file must be specified with "
              "the -c option.")
        sys.exit()

    if not options.rpmdirs and not options.yumrepos:
        print("One of --rpmdirs and --yumrepos must be specified")
        sys.exit(1)

    # Set up list of directories to search
    if options.rpmdirs:
        search_dirs = []
        for d in options.rpmdirs.split(','):
            search_dirs += glob.glob(d)
        if options.verbose:
            print("The following directories will be scanned:")
            for d in search_dirs:
                print("    %s" % d)

    # Setup list of repos
    if options.yumrepos:
        repos = []
        for r in options.yumrepos.split(','):
            repos.append(r)
        if options.verbose:
            print("The following repositories will be scanned:")
            for d in repos:
                print("    %s" % d)

    if options.outfile:
        output = file(options.outfile, "w")
    else:
        output = sys.stdout

    package_dict = {}

    main()
