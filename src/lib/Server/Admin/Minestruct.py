import lxml.etree
import sys

import argparse
from metargs import Option

import Bcfg2.Server.Admin
import Bcfg2.Options

class Minestruct(Bcfg2.Server.Admin.StructureMode):
    """Pull extra entries out of statistics."""
    __shorthelp__ = "Extract extra entry lists from statistics"
    __longhelp__ = (__shorthelp__ +
                    "\n\nbcfg2-admin minestruct [-f filename] "
                    "[-g groups] client\n")
    __usage__ = ("bcfg2-admin minestruct [options] <client>\n\n"
                 "     %-25s%s\n"
                 "     %-25s%s\n" %
                ("-f <filename>",
                 "build a particular file",
                 "-g <lroups>",
                 "only build config for groups"))

    def __init__(self):
        Bcfg2.Server.Admin.StructureMode.__init__(self)
        Bcfg2.Options.add_options(
            Option('-f', '--file', metavar='filename', help='Build a particular file',
                   type=argparse.FileType('w'), default=sys.stdout),
            Option('-g', '--groups', metavar='groups', type=lambda x: x.split(':'),
                   help='Only build config for groups', default=[]),
            Option('client', help='Client to build'),
        )
        Bcfg2.Options.set_help(self.__shorthelp__)

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)

        try:
            extra = set()
            for source in self.bcore.pull_sources:
                for item in source.GetExtra(args.client):
                    extra.add(item)
        except:
            self.log.error("Failed to find extra entry info for client %s" %
                            args.client)
            raise SystemExit(1)
        root = lxml.etree.Element("Base")
        self.log.info("Found %d extra entries" % (len(extra)))
        add_point = root
        for g in args.groups:
            add_point = lxml.etree.SubElement(add_point, "Group", name=g)
        for tag, name in extra:
            self.log.info("%s: %s" % (tag, name))
            lxml.etree.SubElement(add_point, tag, name=name)

        tree = lxml.etree.ElementTree(root)
        tree.write(args.file, pretty_print=True)
