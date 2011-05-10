#!/usr/bin/python
"""Program to generate a bcfg2 Pkgmgr configuration file from a list
   of directories that contain RPMS.

   All versions or only the latest may be included in the output.
   rpm.labelCompare is used to compare the package versions, so that
   a proper rpm version comparison is done (epoch:version-release).

   The output file may be formated for use with the RPM or Yum
   bcfg2 client drivers.  The output can also contain the PackageList
   and nested group headers.
"""
__revision__ = '$Revision: $'
import collections
import datetime
import glob
import gzip
import optparse
import os
import rpm
import sys
from lxml.etree import parse
import xml.sax
from xml.sax.handler import ContentHandler

# Compatibility imports
from Bcfg2.Bcfg2Py3k import urljoin


def info(object, spacing=10, collapse=1):
    """Print methods and doc strings.
       Takes module, class, list, dictionary, or string.
    """
    methodList = [method for method in dir(object)
                  if isinstance(getattr(object, method),
                                collections.Callable)]
    processFunc = collapse and (lambda s: " ".join(s.split())) or (lambda s: s)
    print("\n".join(["%s %s" %
                      (method.ljust(spacing),
                       processFunc(str(getattr(object, method).__doc__)))
                     for method in methodList]))


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

        a and b are dictionaries as created by loadRpms().  Comparison is made
        by package name and then by the full rpm version (epoch, version, release).
        rpm.labelCompare is used for the version part of the comparison.
    """
    n1 = str(a['name'])
    e1 = str(a['epoch'])
    v1 = str(a['version'])
    r1 = str(a['release'])
    n2 = str(b['name'])
    e2 = str(b['epoch'])
    v2 = str(b['version'])
    r2 = str(b['release'])

    ret = cmp(n1, n2)
    if ret == 0:
        ret = rpm.labelCompare((e1, v1, r1), (e2, v2, r2))
    return ret


def loadRpms(dirs):
    """
       dirs is a list of directories to search for rpms.

       Builds a dictionary keyed by the package name.  Dictionary item is a list,
       one entry per package instance found.

       The list entries are dictionaries.  Keys are 'filename', 'mtime' 'name',
       'arch', 'epoch', 'version' and 'release'.

       e.g.

       packages = {
       'bcfg2' : [
           {'filename':'bcfg2-0.9.2-0.0rc1.noarch.rpm', 'mtime':'' 'name':"bcfg2',
            ''arch':'noarch', 'epoch':None, 'version':'0.9.2', 'release':'0.0rc1'}
           {'filename':'bcfg2-0.9.2-0.0rc5.noarch.rpm', 'mtime':'' 'name':"bcfg2',
            ''arch':'noarch', 'epoch':None, 'version':'0.9.2', 'release':'0.0rc5'}],
       'bcfg2-server' : [
           {'filename':'bcfg2-server-0.9.2-0.0rc1.noarch.rpm', 'mtime':'' 'name':"bcfg2-server',
            ''arch':'noarch', 'epoch':None, 'version':'0.9.2', 'release':'0.0rc1'}
           {'filename':'bcfg2-server-0.9.2-0.0rc5.noarch.rpm', 'mtime':'' 'name':"bcfg2-server',
            ''arch':'noarch', 'epoch':None, 'version':'0.9.2', 'release':'0.0rc5'}],
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

            # Only load RPMs with subarchitectures as calculated from the --archs option.
            if subarch in subarchs or 'all' in subarchs:

                # Store what we want in our structure.
                packages.setdefault(name, []).append({'filename': file,
                                                      'mtime': file_mtime,
                                                      'name': name,
                                                      'arch': subarch,
                                                      'epoch': epoch,
                                                      'version': version,
                                                      'release': release})

            # Print '.' for each package. stdio is line buffered, so have to flush it.
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


class PrimaryParser(ContentHandler):
    def __init__(self, packages):
        self.inPackage = 0
        self.inName = 0
        self.inArch = 0
        self.packages = packages

    def startElement(self, name, attrs):
        if name == "package":
            self.package = {'file': None, 'name': '', 'subarch': '',
                            'epoch': None, 'version': None, 'release': None}
            self.inPackage = 1
        elif self.inPackage:
            if name == "name":
                self.inName = 1
            elif name == "arch":
                self.inArch = 1
            elif name == "version":
                self.package['epoch'] = attrs.getValue('epoch')
                self.package['version'] = attrs.getValue('ver')
                self.package['release'] = attrs.getValue('rel')
            elif name == "location":
                self.package['file'] = attrs.getValue('href')

    def endElement(self, name):
        if name == "package":
            self.inPackage = 0
            # Only load RPMs with subarchitectures as calculated from the --archs option.
            if self.package['subarch'] in subarchs or 'all' in subarchs:
                self.packages.setdefault(self.package['name'], []).append(
                    {'filename': self.package['file'],
                     'name': self.package['name'],
                     'arch': self.package['subarch'],
                     'epoch': self.package['epoch'],
                     'version': self.package['version'],
                     'release': self.package['release']})
            # Print '.' for each package. stdio is line buffered, so have to flush it.
            if options.verbose:
                sys.stdout.write('.')
                sys.stdout.flush()
        elif self.inPackage:
            if name == "name":
                self.inName = 0
            elif name == "arch":
                self.inArch = 0

    def characters(self, content):
        if self.inPackage:
            if self.inName:
                self.package['name'] += content
            if self.inArch:
                self.package['subarch'] += content


def loadRepos(repolist):
    '''
       repolist is a list of urls to yum repositories.

       Builds a dictionary keyed by the package name.  Dictionary item is a list,
       one entry per package instance found.

       The list entries are dictionaries.  Keys are 'filename', 'mtime' 'name',
       'arch', 'epoch', 'version' and 'release'.

       e.g.

       packages = {
       'bcfg2' : [
           {'filename':'bcfg2-0.9.2-0.0rc1.noarch.rpm', 'mtime':'' 'name':"bcfg2',
            ''arch':'noarch', 'epoch':None, 'version':'0.9.2', 'release':'0.0rc1'}
           {'filename':'bcfg2-0.9.2-0.0rc5.noarch.rpm', 'mtime':'' 'name':"bcfg2',
            ''arch':'noarch', 'epoch':None, 'version':'0.9.2', 'release':'0.0rc5'}],
       'bcfg2-server' : [
           {'filename':'bcfg2-server-0.9.2-0.0rc1.noarch.rpm', 'mtime':'' 'name':"bcfg2-server',
            ''arch':'noarch', 'epoch':None, 'version':'0.9.2', 'release':'0.0rc1'}
           {'filename':'bcfg2-server-0.9.2-0.0rc5.noarch.rpm', 'mtime':'' 'name':"bcfg2-server',
            ''arch':'noarch', 'epoch':None, 'version':'0.9.2', 'release':'0.0rc5'}],
       }

    '''
    packages = {}
    for repo in repolist:
        url = urljoin(repo, './repodata/repomd.xml')

        if options.verbose:
            print("Loading repo metadata : %s" % url)

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
            if element.tag.endswith('data') and element.get('type') == 'primary':
                for property in element:
                    if property.tag.endswith('location'):
                        primaryhref = property.get('href')

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
        except IOError:
            print("ERROR: Unable to parse retrieved file.")
            sys.exit()

        parser = xml.sax.make_parser()
        parser.setContentHandler(PrimaryParser(packages))
        parser.parse(repo_file)

        if options.verbose:
            sys.stdout.write('\n')
        repo_file.close()
    return packages


def printInstance(instance, group_count):
    """
        Print the details for a package instance with the appropriate indentation and
        in the specified format (rpm or yum).
    """
    group_count = group_count + 1
    name = instance['name']
    epoch = instance['epoch']
    version = instance['version']
    release = instance['release']
    arch = instance['arch']

    output_line = ''
    if options.format == 'rpm':
        output_line = '%s<Instance simplefile=\'%s\' ' % (indent * group_count, instance['filename'])
    else:
        output_line = '%s<Instance ' % (indent * group_count)

    if epoch:
        output_line += 'epoch=\'%s\' ' % (epoch)

    output_line += 'version=\'%s\' release=\'%s\' arch=\'%s\'/>\n' % (version, release, arch)
    output.write(output_line)


def printPackage(entry, group_count):
    """
       Print the details of a package with the appropriate indentation.
       Only the specified (all or latest) release(s) is printed.

       entry is a single package entry as created in loadRpms().
    """
    output.write('%s<Package name=\'%s\' type=\'%s\'>\n' \
                  % (group_count * indent, entry[0]['name'], options.format))

    subarch_dict = {}
    arch_dict = {}
    # Split instances of this package into subarchitectures.
    for instance in entry:
        if instance['arch'] == 'src':
            continue

        if instance['arch'] in subarch_dict:
            subarch_dict[instance['arch']].append(instance)
        else:
            subarch_dict[instance['arch']] = [instance]

        # Keep track of the subarchitectures we have found in each architecture.
        if subarch_mapping[instance['arch']] in arch_dict:
            if instance['arch'] not in arch_dict[subarch_mapping[instance['arch']]]:
                arch_dict[subarch_mapping[instance['arch']]].append(instance['arch'])
        else:
            arch_dict[subarch_mapping[instance['arch']]] = [instance['arch']]

    # Only keep the 'highest' subarchitecture in each architecture.
    for arch in list(arch_dict.keys()):
        if len(arch_dict[arch]) > 1:
            arch_dict[arch].sort()
            for s in arch_dict[arch][:-1]:
                del subarch_dict[s]

    # Sort packages within each architecture into version order
    for arch in subarch_dict:
        subarch_dict[arch].sort(cmpRpmHeader)

        if options.release == 'all':
            # Output all instances
            for header in subarch_dict[arch]:
                printInstance(header, group_count)
        else:
            # Output the latest
            printInstance(subarch_dict[arch][-1], group_count)

    output.write('%s</Package>\n' % (group_count * indent))


def main():

    if options.verbose:
        print("Loading package headers")

    if options.rpmdirs:
        package_dict = loadRpms(search_dirs)
    elif options.yumrepos:
        package_dict = loadRepos(repos)

    if options.verbose:
        print("Processing package headers")

    if options.pkgmgrhdr:
        if options.format == "rpm":
            output.write("<PackageList uri='%s' priority='%s' type='rpm'>\n" % (options.uri, options.priority))
        else:
            output.write("<PackageList priority='%s' type='yum'>\n" % (options.priority))

    group_count = 1
    if groups_list:
        for group in groups_list:
            output.write("%s<Group name='%s'>\n" % (indent * group_count, group))
            group_count = group_count + 1

    # Process packages in name order
    for package_entry in sortedDictValues(package_dict):
        printPackage(package_entry, group_count)

    if groups_list:
        group_count = group_count - 1
        while group_count:
            output.write('%s</Group>\n' % (indent * group_count))
            group_count = group_count - 1

    if options.pkgmgrhdr:
        output.write('</PackageList>\n')

    if options.verbose:
        print("%i package instances were processed" % len(package_dict))


if __name__ == "__main__":

    p = optparse.OptionParser()

    p.add_option('--archs', '-a',  action='store', \
                                   default='all', \
                                   type='string', \
                                   help='''Comma separated list of subarchitectures to include.
                                           The highest subarichitecture required in an
                                           architecture group should specified.   Lower
                                           subarchitecture packages will be loaded if that
                                           is all that is available. e.g. The higher of i386,
                                           i486 and i586 packages will be loaded if -a i586
                                           is specified. (Default: all).
                                        ''')

    p.add_option('--rpmdirs', '-d', action='store',
                                   type='string', \
                                   help='''Comma separated list of directories to scan for RPMS.
                                           Wilcards are permitted.
                                        ''')

    p.add_option('--enddate', '-e', action='store', \
                                   type='string', \
                                   help='End date for RPM file selection.')

    p.add_option('--format', '-f', action='store', \
                                   default='yum', \
                                   type='choice', \
                                   choices=('yum', 'rpm'), \
                                   help='''Format of the Output. Choices are yum or rpm.
                                           (Default: yum)
                                        ''')

    p.add_option('--groups', '-g', action='store', \
                                   type='string', \
                                   help='''List of comma separated groups to nest Package
                                           entities in.
                                        ''')

    p.add_option('--indent', '-i', action='store', \
                                   default=4, \
                                   type='int', \
                                   help='''Number of leading spaces to indent nested entries in the
                                           output. (Default:4)
                                        ''')

    p.add_option('--outfile', '-o', action='store', \
                                   type='string', \
                                   help='Output file name.')

    p.add_option('--pkgmgrhdr', '-P', action='store_true', \
                                   help='Include PackageList header in output.')

    p.add_option('--priority', '-p', action='store', \
                                   default=0, \
                                   type='int', \
                                   help='''Value to set priority attribute in the PackageList Tag.
                                           (Default: 0)
                                        ''')

    p.add_option('--release', '-r', action='store', \
                                   default='latest', \
                                   type='choice', \
                                   choices=('all', 'latest'), \
                                   help='''Which releases to include in the output. Choices are
                                           all or latest.  (Default: latest).''')

    p.add_option('--startdate', '-s', action='store', \
                                   type='string', \
                                   help='Start date for RPM file selection.')

    p.add_option('--uri', '-u',    action='store', \
                                   type='string', \
                                   help='URI for PackageList header required for RPM format ouput.')

    p.add_option('--verbose', '-v', action='store_true', \
                                    help='Enable verbose output.')

    p.add_option('--yumrepos', '-y', action='store',
                                   type='string', \
                                   help='''Comma separated list of YUM repository URLs to load.
                                           NOTE: Each URL must end in a '/' character.''')

    options, arguments = p.parse_args()

    if options.pkgmgrhdr and options.format == 'rpm' and not options.uri:
        print("Option --uri must be specified to produce a PackageList Tag "
              "for rpm formatted files.")
        sys.exit(1)

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

    # Set up list of architectures to include and some mappings
    # to use later.
    arch_mapping = {'x86': ['i686', 'i586', 'i486', 'i386', 'athlon'],
                    'x86_64': ['x86_64'],
                    'ia64': ['ia64'],
                    'ppc': ['ppc'],
                    'ppc64': ['ppc64'],
                    'sparc': ['sparc'],
                    'noarch': ['noarch']}
    subarch_mapping = {'i686': 'x86',
                       'i586': 'x86',
                       'i486': 'x86',
                       'i386': 'x86',
                       'athlon': 'x86',
                       'x86_64': 'x86_64',
                       'ia64': 'ia64',
                       'ppc': 'ppc',
                       'ppc64': 'ppc64',
                       'sparc': 'sparc',
                       'noarch': 'noarch'}
    commandline_subarchs = options.archs.split(',')
    arch_list = []
    subarchs = []
    if 'all' in commandline_subarchs:
        subarchs.append('all')
    else:
        for s in commandline_subarchs:
            if s not in subarch_mapping:
                print("Error: Invalid subarchitecture specified: ", s)
                sys.exit(1)
            # Only allow one subarchitecture per architecture to be specified.
            if s not in arch_list:
                arch_list.append(s)

                # Add subarchitectures lower than the one specified to the list.
                # e.g. If i486 is specified this will add i386 to the list of
                # subarchitectures to load.
                i = arch_mapping[subarch_mapping[s]].index(s)
                #if i != len(arch_mapping[subarch_mapping[s]]):
                subarchs += arch_mapping[subarch_mapping[s]][i:]
            else:
                print("Error: Multiple subarchitecutes of the same "
                      "architecture specified.")
                sys.exit(1)

    indent = ' ' * options.indent

    if options.groups:
        groups_list = options.groups.split(',')
    else:
        groups_list = None

    if options.outfile:
        output = file(options.outfile, "w")
    else:
        output = sys.stdout

    main()
