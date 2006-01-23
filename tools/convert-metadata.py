#!/usr/bin/env python

import glob
import os
import stat
import sys
import lxml.etree

def create_if_noent(name):
    if name[0] != '/':
        name = os.getcwd() + '/' + name
    for count in range(len(name.split('/')))[1:]:
        partial = '/'.join(name.split('/')[:count+1])
        try:
            os.stat(partial)
        except:
            os.mkdir(partial)

def pretty_print(element, level=0):
    '''Produce a pretty-printed text representation of element'''
    if isinstance(element, lxml.etree._Comment):
        return (level * " ") + lxml.etree.tostring(element)
    if element.text:
        fmt = "%s<%%s %%s>%%s</%%s>" % (level*" ")
        data = (element.tag, (" ".join(["%s='%s'" % (key, element.attrib[key]) for key in element.attrib])),
                element.text, element.tag)
    numchild = len(element.getchildren())
    if numchild:
        fmt = "%s<%%s %%s>\n" % (level*" ",) + (numchild * "%s") + "%s</%%s>\n" % (level*" ")
        data = (element.tag, ) + (" ".join(["%s='%s'" % (key, element.attrib[key]) for key in element.attrib]),)
        data += tuple([pretty_print(entry, level+2) for entry in element.getchildren()]) + (element.tag, )
    else:
        fmt = "%s<%%s %%s/>\n" % (level * " ")
        data = (element.tag, " ".join(["%s='%s'" % (key, element.attrib[key]) for key in element.attrib]))
    return fmt % data

if __name__ == '__main__':
    try:
        [source, dest] = sys.argv[1:3]
    except ValueError:
        print "Usage: convert-metadata.py <oldpath> <newpath>"
        raise SystemExit, 1
    contained = {}
    create_if_noent(dest)
    mdata = lxml.etree.parse(source + '/etc/metadata.xml')
    newm = lxml.etree.Element("Groups", version='3.0')
    newc = lxml.etree.Element("Clients", version='3.0')
    newi = lxml.etree.Element("Images", version='3.0')
    names = [block.get('name') for block in mdata.getroot().findall('.//Profile')]
    for block in mdata.getroot().getchildren():
        if block.tag == 'Profile':
            newp = lxml.etree.SubElement(newm, 'Group', profile='true', name=block.get('name'),
                                         public=block.get('public', 'false'))
        elif block.tag == 'Client':
            lxml.etree.SubElement(newc, 'Client', name=block.get('name'), profile=block.get('profile'),
                                  pingable='N', pingtime='0')
            continue
        elif block.tag == 'Class':
            if block.get('name') in names:
                print "%s is a dup profile/class; collapsing" % (block.get('name'))
                newp = newm.xpath('./Group[@name="%s"]' % block.get('name'))[0]
                try:
                    oldincl = newp.xpath('./Group[@name="%s"]' % block.get('name'))[0]
                    newp.remove(oldincl)
                except:
                    print "failed to locate old class inclusion for %s" % (block.get('name'))
            else:
                newp = lxml.etree.SubElement(newm, 'Group', profile='false', name=block.get('name'))
        elif block.tag == 'Image':
            newi.append(block)
            continue
        elif block.tag == None:
            continue
        else:
            print "Unknown block tag %s" % block.tag
            continue
        for child in block.getchildren():
            if child.tag == 'Class':
                lxml.etree.SubElement(newp, 'Group', name=child.get('name'))
                if contained.has_key(child.get('name')):
                    contained[child.get('name')].append(block.get('name'))
                else:
                    contained[child.get('name')] = [block.get('name')]
            elif child.tag == 'Attribute':
                lxml.etree.SubElement(newp, 'Group', name=child.get('name'), scope=child.get('scope'))
            elif child.tag == 'Bundle':
                lxml.etree.SubElement(newp, "Bundle", name=child.get('name'))
            else:
                print "Unknown child tag %s" % child.tag

    iinfo = lxml.etree.parse(source + '/etc/imageinfo.xml')
    for system in iinfo.findall('./System'):
        if system.get('name') == 'debian':
            lxml.etree.SubElement(newm, 'Group', name=system.get('name'), toolset='debian')
        elif system.get('name') == 'redhat':
            lxml.etree.SubElement(newm, 'Group', name=system.get('name'), toolset='rh')
        elif system.get('name') == 'solaris':
            lxml.etree.SubElement(newm, 'Group', name=system.get('name'), toolset='solaris')
        else:
            lxml.etree.SubElement(newm, 'Group', name=system.get('name'))
        for image in system.findall('./Image'):
            newi = lxml.etree.SubElement(newm, 'Group', name=image.get('name'))
            lxml.etree.SubElement(newi, 'Group', name=system.get('name'))

    create_if_noent(dest)
    create_if_noent(dest + '/Metadata')
    open(dest + '/Metadata/groups.xml', 'w').write(pretty_print(newm))
    open(dest + '/Metadata/clients.xml', 'w').write(pretty_print(newc))

    print "*** Image interpolation is not performed automatically"

    bsrc = source + '/Bundler/'
    bdst = dest + '/Bundler/'
    create_if_noent(bdst)
    for bundle in glob.glob(bsrc + '*.xml'):
        bname = bundle.split('/')[-1]
        bdata = lxml.etree.parse(bundle).getroot()
        for sys in bdata.findall('./System'):
            sys.tag = 'Group'
        open(bdst + bname, 'w').write(pretty_print(bdata))

    os.system("rsync -a %s/SSHbase %s > /dev/null" % (source, dest))
    create_if_noent("%s/etc" % ( dest))
    os.system("cp %s/etc/*report*xml %s/etc" % (source, dest))
    os.system("cp %s/etc/statistics.xml %s/etc" % (source, dest))

    # handle base
    basedata = lxml.etree.parse("%s/etc/base.xml" % source)
    left = basedata.getroot().getchildren()
    while left:
        next = left.pop()
        if next.tag in ['Image', 'Class']:
            next.tag = 'Group'
        left += next.getchildren()

    create_if_noent("%s/Base" % dest)
    open(dest + '/Base/converted.xml', 'w').write(pretty_print(basedata.getroot()))

    # handle packages
    create_if_noent("%s/Pkgmgr" % dest)
    for pkgsrc in glob.glob("%s/Pkgmgr/*.xml" % source):
        pname = pkgsrc.split('/')[-1]
        pdata = lxml.etree.parse(pkgsrc).getroot()
        image = pdata.get('image')
        del pdata.attrib['image']
        for loc in pdata.findall('./Location'):
            loc.tag = 'Group'
            loc.set('name', image)
            if loc.attrib.has_key('uri'):
                pdata.set('uri', loc.get('uri'))
                del loc.attrib['uri']
            if loc.attrib.has_key('type'):
                pdata.set('type', loc.get('type'))
                del loc.attrib['type']
        pdata.set('priority', '0')
        open(dest + '/Pkgmgr/' + pname, 'w').write(pretty_print(pdata))

    # handle services.xml
    svcdata = lxml.etree.parse("%s/etc/services.xml" % source)
    left = svcdata.getroot().getchildren()
    while left:
        next = left.pop()
        if next.tag in ['Image', 'Class']:
            next.tag = 'Group'
        left += next.getchildren()

    svcdata.getroot().set('priority', '0')
    create_if_noent("%s/Svcmgr" % dest)
    open(dest + '/Svcmgr/converted.xml', 'w').write(pretty_print(svcdata.getroot()))

    # handle Cfg
    os.chdir("%s/Cfg" % source)
    p = os.popen("find . -depth -type d -print")
    path = p.readline().strip()
    paths = []
    while path:
        paths.append(path)
        create_if_noent("%s/Cfg/%s" % (dest, path))
        path = p.readline().strip()
    # paths are now created
    for path in paths:
        for filename in os.listdir(path):
            if stat.S_ISDIR(os.stat(path + '/' + filename)[stat.ST_MODE]):
                continue
            if filename in [':info', path.split('/')[-1]]:
                os.system("cp -f %s/%s %s/Cfg/%s/%s" % (path, filename, dest, path, filename))
            else:
                meta = filename[len(path.split('/')[-1])+1:]
                if meta[:2] == 'H_':
                    os.system("cp -f %s/%s %s/Cfg/%s/%s" % (path, filename, dest, path, filename))
                elif meta[:1] in ['C', 'B', 'I']:
                    print filename, "moved"
                    meta = 'G' + meta[1:]
                    os.system("cp -f %s/%s %s/Cfg/%s/%s.%s" % (path, filename, dest,
                                                                    path, path.split('/')[-1], meta))
                else:
                    print "=========> don't know what to do with %s/%s" % (path, filename)

