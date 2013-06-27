#!/usr/bin/env python

import os
import sys
import lxml.etree

import Bcfg2.Options

def main():
    parser = Bcfg2.Options.get_parser(
        description="Migrate from Bcfg2 1.1-style Properties-based NagiosGen "
        "configuration to standalone 1.2-style")
    parser.add_options([Bcfg2.Options.Common.repository])
    parser.parse()

    repo = Bcfg2.Options.setup.repository
    oldconfigfile = os.path.join(repo, 'Properties', 'NagiosGen.xml')
    newconfigpath = os.path.join(repo, 'NagiosGen')
    newconfigfile = os.path.join(newconfigpath, 'config.xml')
    parentsfile   = os.path.join(newconfigpath, 'parents.xml')

    if not os.path.exists(oldconfigfile):
        print("%s does not exist, nothing to do" % oldconfigfile)
        return 1

    if not os.path.exists(newconfigpath):
        print("%s does not exist, cannot write %s" %
              (newconfigpath, newconfigfile))
        return 2

    newconfig = lxml.etree.XML("<NagiosGen/>")

    oldconfig = lxml.etree.parse(oldconfigfile)
    for host in oldconfig.getroot().getchildren():
        if host.tag == lxml.etree.Comment:
            # skip comments
            continue

        if host.tag == 'default':
            print("default tag will not be converted; use a suitable Group tag instead")
            continue

        newhost = lxml.etree.Element("Client", name=host.tag)
        for opt in host:
            newopt = lxml.etree.Element("Option", name=opt.tag)
            newopt.text = opt.text
            newhost.append(newopt)
        newconfig.append(newhost)

    # parse the parents config, if it exists
    if os.path.exists(parentsfile):
        parentsconfig = lxml.etree.parse(parentsfile)
        for el in parentsconfig.xpath("//Depend"):
            newhost = newconfig.find("Client[@name='%s']" % el.get("name"))
            if newhost is not None:
                newparents = newhost.find("Option[@name='parents']")
                if newparents is not None:
                    newparents.text += "," + el.get("on")
                else:
                    newparents = lxml.etree.Element("Option", name="parents")
                    newparents.text = el.get("on")
                    newhost.append(newparents)
            else:
                newhost = lxml.etree.Element("Client", name=el.get("name"))
                newparents = lxml.etree.Element("Option", name="parents")
                newparents.text = el.get("on")
                newhost.append(newparents)
                newconfig.append(newhost)

    try:
        open(newconfigfile, 'w').write(lxml.etree.tostring(newconfig,
                                                           pretty_print=True))
        print("%s written" % newconfigfile)
    except IOError:
        print("Failed to write %s" % newconfigfile)

if __name__ == '__main__':
    sys.exit(main())
