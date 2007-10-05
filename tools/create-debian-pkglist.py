#!/usr/bin/env python

'''Build debian/ubuntu package indexes'''
__revision__ = '$Id: $'

import glob, gzip, lxml.etree, os, re, urllib, cStringIO, sys

def debug(msg):
    '''print debug messages'''
    if '-v' in sys.argv:
        sys.stdout.write(msg)


def processSource(prefix, source, dists, archs, prio, groups, packages):
    '''Build package indices for source'''
    filename = "%s/%s.xml" % (prefix, source.replace('/', '_'))
    try:
        os.stat(filename)
        filename += '~'
    except:
        pass
    output = open(filename, 'w')
    #depfile = open(filename + '-deps', 'w')
    groupinfo = "".join(['<Group name="%s">' % group for group in groups])
    output.write('<PackageList priority="%s" type="deb">%s\n' % (prio, groupinfo))
    for dist in dists:
        pkgdata = {}
        pkgdeps = {}
        for arch in archs:
            url = "%s/%s/binary-%s/Packages.gz" % (source, dist, arch)
            debug("Processing url %s\n" % (url))
            data = urllib.urlopen(url)
            buf = cStringIO.StringIO(''.join(data.readlines()))
            reader = gzip.GzipFile(fileobj=buf)
            for line in reader.readlines():
                if line[:8] == 'Package:':
                    pkgname = line.split(' ')[1].strip()
                elif line[:8] == 'Version:':
                    version = line.split(' ')[1].strip()
                    if pkgdata.has_key(pkgname):
                        pkgdata[pkgname][arch] = version
                    else:
                        pkgdata[pkgname] = {arch:version}
                elif line[:8] == 'Depends:':
                    deps = re.sub(',', '', re.sub('\(.*\)', '', line)).split()[1:]
                    if pkgdeps.has_key(pkgname):
                        pkgdeps[pkgname][arch] = deps
                    else:
                        pkgdeps[pkgname] = {arch:deps}
                else:
                    continue
        coalesced = 0
        for pkg in pkgdata.keys():
            data = pkgdata[pkg].values()
            if data.count(data[0]) == len(data) == len(archs):
                output.write('<Package name="%s" version="%s"/>\n' % (pkg, data[0]))
                coalesced += 1
                del pkgdata[pkg]
        for pkg in pkgdeps.keys():
            data = pkgdeps[pkg].values()
            if data.count(data[0]) == len(data):
                elt = lxml.etree.Element("Package", name=pkg)
                [lxml.etree.SubElement(elt, "Package", name=dep) for dep in data[0]]
                #depfile.write(lxml.etree.tostring(elt) + '\n')
                del pkgdeps[pkg]
        # now we need to do per-arch entries
        perarch = 0
        if pkgdata:
            for arch in archs:
                output.write('<Group name="%s">\n' % (arch))
                for pkg in pkgdata.keys():
                    if pkgdata[pkg].has_key(arch):
                        output.write('<Package name="%s" version="%s"/>\n' % (pkg, pkgdata[pkg][arch]))
                        perarch += 1
                output.write('</Group>\n')
        debug("Got %s coalesced, %s per-arch\n" % (coalesced, perarch))
    closegroup = "".join(['</Group>' for group in groups])
    output.write('%s</PackageList>\n' % (closegroup))
    output.close()
    #depfile.close()
    if filename[-1] == '~':
        old = open(filename[:-1]).read()
        new = open(filename).read()
        if old != new:
            debug("%s has changed; installing new version\n" % (filename[:-1]))
            os.rename(filename, filename[:-1])
        else:
            debug("%s has not changed\n" % (filename[:-1]))

if __name__ == '__main__':
    hprefix = '/tmp'
    rprefix = '/home/desai/data/bcfg2'
    packages = []
    for fn in glob.glob("%s/Bundler/*.xml" % rprefix) + glob.glob("%s/Base/*.xml" % rprefix):
        doc = lxml.etree.parse(fn)
        [packages.append(pkg.get('name')) for pkg in doc.findall('.//Package') if
         pkg.get('name') not in packages]
        
    print len(packages)

    SOURCES = [('http://security.debian.org/dists/stable/updates',
                ['main', 'contrib', 'non-free'], ['i386'], '10', ['debian-sarge']),
               ('http://volatile.debian.net/debian-volatile/dists/stable/volatile',
                ['main', 'contrib', 'non-free'], ['i386'], '20', ['debian-sarge']),
               ('http://us.archive.ubuntu.com/ubuntu/dists/dapper',
                ['main', 'multiverse', 'universe'], ['i386', 'amd64'], 0, ['ubuntu-dapper']),
               ('http://netzero.mcs.anl.gov/disks/distro/ubuntu/dists/dapper',
                ['main', 'multiverse', 'universe'], ['i386', 'amd64'], 0, ['ubuntu-dapper'])]

    for src, dsts, ars, pri, grps in SOURCES:
        processSource(hprefix, src, dsts, ars, pri, grps, packages)
