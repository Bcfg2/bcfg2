#!/usr/bin/env python

from copy import deepcopy
import lxml.etree
import os

import Bcfg2.Options

"""
NOTE: This script takes a conservative approach when it comes to
      updating your Rules. It creates a new unified-rules.xml file
      without the attributes you have defined in your current rules. The
      reason for this is to keep this script simple so we don't have
      to go through and determine the priorities associated with your
      current rules definitions.
"""

if __name__ == '__main__':
    Bcfg2.Options.add_options(
        Bcfg2.Options.SERVER_REPOSITORY
    )
    args = Bcfg2.Options.args()
    repo = args.repository_path
    unifiedposixrules = "%s/Rules/unified-rules.xml" % repo
    rulesroot = lxml.etree.Element("Rules")

    for plug in ['Base', 'Bundler']:
        for root, dirs, files in os.walk('%s/%s' % (repo, plug)):
            if '.svn' in dirs:
                dirs.remove('.svn')
            for filename in files:
                if filename.startswith('new'):
                    continue
                xdata = lxml.etree.parse(os.path.join(root, filename))
                # replace ConfigFile elements
                for c in xdata.findall('//ConfigFile'):
                    parent = c.getparent()
                    oldc = c
                    c.tag = 'Path'
                    parent.replace(oldc, c)
                # replace Directory elements
                for d in xdata.findall('//Directory'):
                    parent = d.getparent()
                    oldd = d
                    d.tag = 'Path'
                    parent.replace(oldd, d)
                    # Create new-style Rules entry
                    newd = deepcopy(d)
                    newd.set('type', 'directory')
                    rulesroot.append(newd)
                # replace BoundDirectory elements
                for d in xdata.findall('//BoundDirectory'):
                    parent = d.getparent()
                    oldd = d
                    d.tag = 'BoundPath'
                    parent.replace(oldd, d)
                    # Create new-style entry
                    newd = deepcopy(d)
                    newd.set('type', 'directory')
                # replace Permissions elements
                for p in xdata.findall('//Permissions'):
                    parent = p.getparent()
                    oldp = p
                    p.tag = 'Path'
                    parent.replace(oldp, p)
                    # Create new-style Rules entry
                    newp = deepcopy(p)
                    newp.set('type', 'permissions')
                    rulesroot.append(newp)
                # replace BoundPermissions elements
                for p in xdata.findall('//BoundPermissions'):
                    parent = p.getparent()
                    oldp = p
                    p.tag = 'BoundPath'
                    parent.replace(oldp, p)
                    # Create new-style entry
                    newp = deepcopy(p)
                    newp.set('type', 'permissions')
                # replace SymLink elements
                for s in xdata.findall('//SymLink'):
                    parent = s.getparent()
                    olds = s
                    s.tag = 'Path'
                    parent.replace(olds, s)
                    # Create new-style Rules entry
                    news = deepcopy(s)
                    news.set('type', 'symlink')
                    rulesroot.append(news)
                # replace BoundSymLink elements
                for s in xdata.findall('//BoundSymLink'):
                    parent = s.getparent()
                    olds = s
                    s.tag = 'BoundPath'
                    parent.replace(olds, s)
                    # Create new-style entry
                    news = deepcopy(s)
                    news.set('type', 'symlink')
                # write out the new bundle
                try:
                    newbundle = open("%s/%s/new%s" % (repo, plug, filename), 'w')
                except IOError:
                    print("Failed to write %s" % filename)
                    continue
                newbundle.write(lxml.etree.tostring(xdata, pretty_print=True))
                newbundle.close()

    try:
        newrules = open(unifiedposixrules, 'w')
        rulesroot.set('priority', '1')
        newrules.write(lxml.etree.tostring(rulesroot, pretty_print=True))
        newrules.close()
    except IOError:
        print("Failed to write %s" % unifiedposixrules)
