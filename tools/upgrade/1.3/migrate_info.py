#!/usr/bin/env python

import os
import re
import sys
import lxml.etree
import Bcfg2.Options
from Bcfg2.Server.Plugin import INFO_REGEX


PERMS_REGEX = re.compile(r'perms:\s*(?P<perms>\w+)')


def convert(info_file):
    info_xml = os.path.join(os.path.dirname(info_file), "info.xml")
    if os.path.exists(info_xml):
        print("%s already exists, not converting %s" % (info_xml, info_file))
        return
    print("Converting %s to %s" % (info_file, info_xml))
    fileinfo = lxml.etree.Element("FileInfo")
    info = lxml.etree.SubElement(fileinfo, "Info")
    for line in open(info_file).readlines():
        match = INFO_REGEX.match(line) or PERMS_REGEX.match(line)
        if match:
            mgd = match.groupdict()
            for key, value in list(mgd.items()):
                if value:
                    info.set(key, value)

    open(info_xml, "w").write(lxml.etree.tostring(fileinfo, pretty_print=True))
    os.unlink(info_file)


def main():
    opts = dict(repo=Bcfg2.Options.SERVER_REPOSITORY,
                configfile=Bcfg2.Options.CFILE,
                plugins=Bcfg2.Options.SERVER_PLUGINS)
    setup = Bcfg2.Options.OptionParser(opts)
    setup.parse(sys.argv[1:])

    for plugin in setup['plugins']:
        if plugin not in ['SSLCA', 'Cfg', 'TGenshi', 'TCheetah', 'SSHbase']:
            continue
        for root, dirs, files in os.walk(os.path.join(setup['repo'], plugin)):
            for fname in files:
                if fname in [":info", "info"]:
                    convert(os.path.join(root, fname))


if __name__ == '__main__':
    sys.exit(main())
