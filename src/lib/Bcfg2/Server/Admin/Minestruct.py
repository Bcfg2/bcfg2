""" Extract extra entry lists from statistics """
import getopt
import lxml.etree
import sys
import Bcfg2.Server.Admin


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
        except:
            self.log.error(self.__doc__)
            raise SystemExit(1)

        client = args[0]
        output = sys.stdout
        groups = []

        for (opt, optarg) in opts:
            if opt == '-f':
                try:
                    output = open(optarg, 'w')
                except IOError:
                    self.log.error("Failed to open file: %s" % (optarg))
                    raise SystemExit(1)
            elif opt == '-g':
                groups = optarg.split(':')

        try:
            extra = set()
            for source in self.bcore.pull_sources:
                for item in source.GetExtra(client):
                    extra.add(item)
        except:
            self.log.error("Failed to find extra entry info for client %s" %
                            client)
            raise SystemExit(1)
        root = lxml.etree.Element("Base")
        self.log.info("Found %d extra entries" % (len(extra)))
        add_point = root
        for grp in groups:
            add_point = lxml.etree.SubElement(add_point, "Group", name=grp)
        for tag, name in extra:
            self.log.info("%s: %s" % (tag, name))
            lxml.etree.SubElement(add_point, tag, name=name)

        lxml.etree.ElementTree(root).write(output, pretty_print=True)
