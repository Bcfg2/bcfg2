#!/usr/bin/env python

import os
import re
import sys
import lxml.etree
import Bcfg2.Options

INFO_REGEX = re.compile(r'owner:\s*(?P<owner>\S+)|' +
                        r'group:\s*(?P<group>\S+)|' +
                        r'mode:\s*(?P<mode>\w+)|' +
                        r'secontext:\s*(?P<secontext>\S+)|' +
                        r'paranoid:\s*(?P<paranoid>\S+)|' +
                        r'sensitive:\s*(?P<sensitive>\S+)|' +
                        r'encoding:\s*(?P<encoding>\S+)|' +
                        r'important:\s*(?P<important>\S+)|' +
                        r'mtime:\s*(?P<mtime>\w+)')


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
    parser = Bcfg2.Options.get_parser(
        description="Migrate from Bcfg2 1.2 info/:info files to 1.3 info.xml")
    parser.add_options([Bcfg2.Options.Common.repository,
                        Bcfg2.Options.Common.plugins])
    parser.parse()

    for plugin in Bcfg2.Options.setup.plugins:
        if plugin not in ['SSLCA', 'Cfg', 'TGenshi', 'TCheetah', 'SSHbase']:
            continue
        datastore = os.path.join(Bcfg2.Options.setup.repository, plugin)
        for root, dirs, files in os.walk(datastore):
            for fname in files:
                if fname in [":info", "info"]:
                    convert(os.path.join(root, fname))


if __name__ == '__main__':
    sys.exit(main())
