#!/usr/bin/env python

import lxml.etree
import os
import sys

import Bcfg2.Options


def setmodeattr(elem):
    """Set the mode attribute for a given element."""
    if elem.attrib.has_key('perms'):
        elem.set('mode', elem.get('perms'))
        del elem.attrib['perms']
        return True
    return False


def writefile(f, xdata):
    """Write xml data to a file"""
    newfile = open(f, 'w')
    newfile.write(lxml.etree.tostring(xdata, pretty_print=True))
    newfile.close()


def convertinfo(ifile):
    """Do perms -> mode conversion for info.xml files."""
    try:
        xdata = lxml.etree.parse(ifile)
    except lxml.etree.XMLSyntaxError:
        err = sys.exc_info()[1]
        print("Could not parse %s, skipping: %s" % (ifile, err))
        return
    found = False
    for i in xdata.findall('//Info'):
        found |= setmodeattr(i)
    if found:
        writefile(ifile, xdata)


def convertstructure(structfile):
    """Do perms -> mode conversion for structure files."""
    try:
        xdata = lxml.etree.parse(structfile)
    except lxml.etree.XMLSyntaxError:
        err = sys.exc_info()[1]
        print("Could not parse %s, skipping: %s" % (structfile, err))
        return
    found = False
    for path in xdata.xpath('//BoundPath|//Path'):
        found |= setmodeattr(path)
    if found:
        writefile(structfile, xdata)


def main():
    opts = dict(repo=Bcfg2.Options.SERVER_REPOSITORY,
                configfile=Bcfg2.Options.CFILE,
                plugins=Bcfg2.Options.SERVER_PLUGINS)
    setup = Bcfg2.Options.OptionParser(opts)
    setup.parse(sys.argv[1:])
    repo = setup['repo']

    for plugin in setup['plugins']:
        if plugin in ['Base', 'Bundler', 'Rules']:
            for root, dirs, files in os.walk(os.path.join(repo, plugin)):
                for fname in files:
                    convertstructure(os.path.join(root, fname))
        if plugin not in ['Cfg', 'TGenshi', 'TCheetah', 'SSHbase', 'SSLCA']:
            continue
        for root, dirs, files in os.walk(os.path.join(repo, plugin)):
            for fname in files:
                if fname == 'info.xml':
                    convertinfo(os.path.join(root, fname))

if __name__ == '__main__':
    sys.exit(main())
