'''Minestruct Admin Mode'''
import Bcfg2.Server.Admin
import lxml.etree, sys, getopt

class Minestruct(Bcfg2.Server.Admin.StructureMode):
    '''Pull extra entries out of statistics'''
    __shorthelp__ = 'bcfg2-admin minestruct [-f file-name] [-g groups] client'
    __longhelp__ = __shorthelp__ + '\n\tExtract extra entry lists from statistics'

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        if len(args) == 0:
            self.errExit("No hostname specified (see bcfg2-admin minestruct -h for help)")
        try:
            (opts, args) = getopt.getopt(args, 'f:g:h')
        except:
            self.log.error(self.__shorthelp__)
            raise SystemExit(1)
        if "-h" in args or not args:
            print "Usage:"
            print self.__shorthelp__
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

        extra = self.statistics.GetExtra(client)
        root = lxml.etree.Element("Base")
        self.log.info("Found %d extra entries" % (len(extra)))
        add_point = root
        for g in groups:
            add_point = lxml.etree.SubElement(add_point, "Group", name=g)
        for tag, name in extra:
            self.log.info("%s: %s" % (tag, name))
            lxml.etree.SubElement(add_point, tag, name=name)

        tree = lxml.etree.ElementTree(root)
        tree.write(output, pretty_print=True)

