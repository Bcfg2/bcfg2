#!/usr/bin/env python

import os
import sys
import glob
import lxml.etree
import Bcfg2.Options

def main():
    opts = dict(repo=Bcfg2.Options.SERVER_REPOSITORY)
    setup = Bcfg2.Options.OptionParser(opts)
    setup.parse(sys.argv[1:])

    files = []
    for plugin in ['Pkgmgr']:
        files.extend(glob.glob(os.path.join(setup['repo'], plugin, "*")))

    for bfile in files:
        bdata = lxml.etree.parse(bfile)
        changed = False

        if not bdata.xpath("//@type='sysv'"):
            print("%s doesn't contain any sysv packages, skipping" % bfile)
            continue

        pkglist = bdata.getroot()
        if pkglist.tag != "PackageList":
            print("%s doesn't look like a PackageList, skipping" % bfile)
            continue

        for pkg in bdata.xpath("//Package"):
            if "simplename" in pkg.attrib:
                pkg.set("simplefile", pkg.get("simplename"))
                del pkg.attrib["simplename"]
                changed = True

        # if we switched to simplefile, we also need to switch to uri
        if changed and "url" in pkglist.attrib:
            pkglist.set("uri", pkglist.get("url"))
            del pkglist.attrib["url"]

        if changed:
            print("Writing %s" % bfile)
            try:
                open(bfile, "w").write(lxml.etree.tostring(bdata))
            except IOError:
                err = sys.exc_info()[1]
                print("Could not write %s: %s" % (bfile, err))

if __name__ == '__main__':
    sys.exit(main())
