#!/usr/bin/env python

import lxml.etree
import os
import sys

import Bcfg2.Options

if __name__ == '__main__':
    opts = {
               'repo': Bcfg2.Options.SERVER_REPOSITORY,
           }
    setup = Bcfg2.Options.OptionParser(opts)
    setup.parse(sys.argv[1:])
    repo = setup['repo']

    for plug in ['Base', 'Bundler']:
        for root, dirs, files in os.walk('%s/%s' % (repo, plug)):
            for filename in files:
                if filename.startswith('new'):
                    continue
                xdata = lxml.etree.parse(os.path.join(root, filename))
                # replace ConfigFile elements
                for c in xdata.findall('//ConfigFile'):
                    parent = c.getparent()
                    oldc = c
                    c.set('type', 'file')
                    c.tag = 'Path'
                    parent.replace(oldc, c)
                # replace Directory elements
                for d in xdata.findall('//Directory'):
                    parent = d.getparent()
                    oldd = d
                    d.set('type', 'directory')
                    d.tag = 'Path'
                    parent.replace(oldd, d)
                # replace Permissions elements
                for p in xdata.findall('//Permissions'):
                    parent = p.getparent()
                    oldp = p
                    p.set('type', 'permissions')
                    p.tag = 'Path'
                    parent.replace(oldp, p)
                # replace SymLink elements
                for s in xdata.findall('//SymLink'):
                    parent = s.getparent()
                    olds = s
                    s.set('type', 'symlink')
                    s.tag = 'Path'
                    parent.replace(olds, s)
                # write out the new bundle
                try:
                    newbundle = open("%s/%s/new%s" % (repo, plug, filename), 'w')
                except IOError:
                    print("Failed to write %s" % filename)
                    continue
                newbundle.write(lxml.etree.tostring(xdata, pretty_print=True))
                newbundle.close()
