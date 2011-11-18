import lxml.etree
import Bcfg2.Server.Admin
from Bcfg2.Server.Plugins.Metadata import MetadataConsistencyError


class Client(Bcfg2.Server.Admin.MetadataCore):
    __shorthelp__ = "Create, delete, or modify client entries"
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin client add <client> "
                                    "attr1=val1 attr2=val2"
                                    "\nbcfg2-admin client update <client> "
                                    "attr1=val1 attr2=val2"
                                    "\nbcfg2-admin client list"
                                    "\nbcfg2-admin client del <client>\n")
    __usage__ = ("bcfg2-admin client [options] [add|del|update|list] [attr=val]")

    def __init__(self, configfile):
        Bcfg2.Server.Admin.MetadataCore.__init__(self, configfile,
                                                 self.__usage__)

    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)
        if len(args) == 0:
            self.errExit("No argument specified.\n"
                         "Please see bcfg2-admin client help for usage.")
        if args[0] == 'add':
            attr_d = {}
            for i in args[2:]:
                attr, val = i.split('=', 1)
                if attr not in ['profile', 'uuid', 'password',
                                'location', 'secure', 'address',
                                'auth']:
                    print("Attribute %s unknown" % attr)
                    raise SystemExit(1)
                attr_d[attr] = val
            try:
                self.metadata.add_client(args[1], attr_d)
            except MetadataConsistencyError:
                print("Error in adding client")
                raise SystemExit(1)
        elif args[0] in ['update', 'up']:
            attr_d = {}
            for i in args[2:]:
                attr, val = i.split('=', 1)
                if attr not in ['profile', 'uuid', 'password',
                                'location', 'secure', 'address',
                                'auth']:
                    print("Attribute %s unknown" % attr)
                    raise SystemExit(1)
                attr_d[attr] = val
            try:
                self.metadata.update_client(args[1], attr_d)
            except MetadataConsistencyError:
                print("Error in updating client")
                raise SystemExit(1)
        elif args[0] in ['delete', 'remove', 'del', 'rm']:
            try:
                self.metadata.remove_client(args[1])
            except MetadataConsistencyError:
                print("Error in deleting client")
                raise SystemExit(1)
        elif args[0] in ['list', 'ls']:
            tree = lxml.etree.parse(self.metadata.data + "/clients.xml")
            tree.xinclude()
            for node in tree.findall("//Client"):
                print(node.attrib["name"])
        else:
            print("No command specified")
            raise SystemExit(1)
