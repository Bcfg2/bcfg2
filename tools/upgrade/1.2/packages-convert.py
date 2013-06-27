#!/usr/bin/env python

import os
import sys
import lxml.etree
from Bcfg2.Compat import ConfigParser
import Bcfg2.Options

XI_NAMESPACE = "http://www.w3.org/2001/XInclude"
XI = "{%s}" % XI_NAMESPACE

def place_source(xdata, source, groups):
    """ given a source's group memberships, place it appropriately
    within the given XML document tree """
    if not groups:
        xdata.append(source)
    else:
        for group in groups:
            match = xdata.xpath("Group[@name='%s']" % group)
            if match:
                groups.remove(group)
                xdata.replace(match[0], place_source(match[0], source, groups))
                return xdata

        # no group found to put this source into
        group = groups.pop()
        xdata.append(place_source(lxml.etree.Element("Group", name=group),
                                  source, groups))

    return xdata

def main():
    parser = Bcfg2.Options.get_parser(
        description="Migrate from Bcfg2 1.1-style Packages configuration to "
        "1.2-style")
    parser.add_options([Bcfg2.Options.Common.repository])
    parser.parse()

    repo = Bcfg2.Options.setup.repository
    configpath = os.path.join(repo, 'Packages')
    oldconfigfile  = os.path.join(configpath, 'config.xml')
    newconfigfile  = os.path.join(configpath, 'packages.conf')
    newsourcesfile = os.path.join(configpath, 'sources.xml')

    if not os.path.exists(oldconfigfile):
        print("%s does not exist, nothing to do" % oldconfigfile)
        return 1

    if not os.path.exists(configpath):
        print("%s does not exist, cannot write %s" % (configpath,
                                                      newconfigfile))
        return 2

    newconfig = ConfigParser.SafeConfigParser()
    newconfig.add_section("global")

    oldconfig = lxml.etree.parse(oldconfigfile).getroot()

    config = oldconfig.xpath('//Sources/Config')
    if config:
        if config[0].get("resolver", "enabled").lower() == "disabled":
            newconfig.add_option("global", "resolver", "disabled")
        if config[0].get("metadata", "enabled").lower() == "disabled":
            newconfig.add_option("global", "metadata", "disabled")
    newconfig.write(open(newconfigfile, "w"))
    print("%s written" % newconfigfile)

    oldsources = [oldconfigfile]
    while oldsources:
        oldfile = oldsources.pop()
        oldsource = lxml.etree.parse(oldfile).getroot()

        if oldfile == oldconfigfile:
            newfile = newsourcesfile
        else:
            newfile = os.path.join(configpath,
                                   oldfile.replace("%s/" % configpath, ''))
        newsource = lxml.etree.Element("Sources", nsmap=oldsource.nsmap)

        for el in oldsource.getchildren():
            if el.tag == lxml.etree.Comment or el.tag == 'Config':
                # skip comments and Config
                continue

            if el.tag == XI + 'include':
                oldsources.append(os.path.join(configpath, el.get('href')))
                newsource.append(el)
                continue

            # element must be a *Source
            newel = lxml.etree.Element("Source",
                                       type=el.tag.replace("Source",
                                                           "").lower())
            try:
                newel.set('recommended', el.find('Recommended').text.lower())
            except AttributeError:
                pass

            for tag in ['RawURL', 'URL', 'Version']:
                try:
                    newel.set(tag.lower(), el.find(tag).text)
                except AttributeError:
                    pass

            for child in el.getchildren():
                if child.tag in ['Component', 'Blacklist', 'Whitelist', 'Arch']:
                    newel.append(child)

            groups = [e.text for e in el.findall("Group")]
            newsource = place_source(newsource, newel, groups)

        try:
            open(newfile, 'w').write(lxml.etree.tostring(newsource,
                                                         pretty_print=True))
            print("%s written" % newfile)
        except IOError:
            print("Failed to write %s" % newfile)

if __name__ == '__main__':
    sys.exit(main())
