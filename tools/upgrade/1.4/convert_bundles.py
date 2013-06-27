#!/usr/bin/env python

import os
import sys
import lxml.etree
import Bcfg2.Options


def main():
    parser = Bcfg2.Options.get_parser("Tool to remove bundle names")
    parser.add_options([Bcfg2.Options.Common.repository])
    parser.parse()

    bundler_dir = os.path.join(Bcfg2.Options.setup.repository, "Bundler")
    if os.path.exists(bundler_dir):
        for root, _, files in os.walk(bundler_dir):
            for fname in files:
                bpath = os.path.join(root, fname)
                newpath = bpath
                if newpath.endswith(".genshi"):
                    newpath = newpath[:-6] + "xml"
                    print("Converting %s to %s" % (bpath, newpath))
                else:
                    print("Converting %s" % bpath)
                xroot = lxml.etree.parse(bpath)
                xdata = xroot.getroot()
                if 'name' in xdata.attrib:
                    del xdata.attrib['name']
                xroot.write(bpath)

if __name__ == '__main__':
    sys.exit(main())
