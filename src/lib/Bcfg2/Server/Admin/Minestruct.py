""" Extract extra entry lists from statistics """
import getopt
import lxml.etree
import sys
import Bcfg2.Server.Admin
from Bcfg2.Server.Plugin import PullSource


class Minestruct(Bcfg2.Server.Admin.StructureMode):
    """ Extract extra entry lists from statistics """
    __usage__ = ("[options] <client>\n\n"
                 "     %-25s%s\n"
                 "     %-25s%s\n" %
                ("-f <filename>", "build a particular file",
                 "-g <groups>", "only build config for groups"))

    def __call__(self, args):
        if len(args) == 0:
            self.errExit("No argument specified.\n"
                         "Please see bcfg2-admin minestruct help for usage.")
        try:
            (opts, args) = getopt.getopt(args, 'f:g:h')
        except getopt.GetoptError:
            self.errExit(self.__doc__)

        client = args[0]
        output = sys.stdout
        groups = []

        for (opt, optarg) in opts:
            if opt == '-f':
                try:
                    output = open(optarg, 'w')
                except IOError:
                    self.errExit("Failed to open file: %s" % (optarg))
            elif opt == '-g':
                groups = optarg.split(':')

        try:
            extra = set()
            for source in self.bcore.plugins_by_type(PullSource):
                for item in source.GetExtra(client):
                    extra.add(item)
        except:  # pylint: disable=W0702
            self.errExit("Failed to find extra entry info for client %s" %
                         client)
        root = lxml.etree.Element("Base")
        self.log.info("Found %d extra entries" % (len(extra)))
        add_point = root
        for grp in groups:
            add_point = lxml.etree.SubElement(add_point, "Group", name=grp)
        for tag, name in extra:
            self.log.info("%s: %s" % (tag, name))
            lxml.etree.SubElement(add_point, tag, name=name)

        lxml.etree.ElementTree(root).write(output, pretty_print=True)
