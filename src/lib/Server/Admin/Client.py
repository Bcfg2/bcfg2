import lxml.etree
import Bcfg2.Server.Admin
from metargs import Option
from Bcfg2.Server.Plugins.Metadata import MetadataConsistencyError
import Bcfg2.Options


class Client(Bcfg2.Server.Admin.MetadataCore):
    __shorthelp__ = "Create, delete, or modify client entries"
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin client add <client> "
                                    "attr1=val1 attr2=val2"
                                    "\nbcfg2-admin client update <client> "
                                    "attr1=val1 attr2=val2"
                                    "\nbcfg2-admin client list"
                                    "\nbcfg2-admin client del <client>\n")
    __usage__ = ("bcfg2-admin client [options] [add|del|update|list] [attr=val]")

    def __init__(self):
        Bcfg2.Server.Admin.MetadataCore.__init__(self)
        Bcfg2.Options.set_help(self.__shorthelp__)

        def split_attr(val):
            return val.split('=', 1)

        Bcfg2.Options.add_option(
            Option('command', help='Client command to execute',
                   choices=['add', 'update', 'up', 'delete', 'remove',
                            'del', 'rm', 'list', 'ls'])
        )
        
        args = Bcfg2.Options.bootstrap()
        
        if args.command not in ['list', 'ls']:
            Bcfg2.Options.add_options(
                Option('client', help='Client to update'),
                Option('attributes', help='Attributes to update', metavar='attr=val',
                       nargs='*', type=split_attr)
            )

    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)
        if args.command == 'add':
            attr_d = {}
            for attr, val in args.attributes:
                if attr not in ['profile', 'uuid', 'password',
                                'location', 'secure', 'address',
                                'auth']:
                    print("Attribute %s unknown" % attr)
                    raise SystemExit(1)
                attr_d[attr] = val
            try:
                self.metadata.add_client(args.client, attr_d)
            except MetadataConsistencyError:
                print("Error in adding client")
                raise SystemExit(1)
        elif args.command in ['update', 'up']:
            attr_d = {}
            for attr, val in args.attributes:
                if attr not in ['profile', 'uuid', 'password',
                                'location', 'secure', 'address',
                                'auth']:
                    print("Attribute %s unknown" % attr)
                    raise SystemExit(1)
                attr_d[attr] = val
            try:
                self.metadata.update_client(args.client, attr_d)
            except MetadataConsistencyError:
                print("Error in updating client")
                raise SystemExit(1)
        elif args.command in ['delete', 'remove', 'del', 'rm']:
            try:
                self.metadata.remove_client(args.client)
            except MetadataConsistencyError:
                print("Error in deleting client")
                raise SystemExit(1)
        elif args.command in ['list', 'ls']:
            tree = lxml.etree.parse(self.metadata.data + "/clients.xml")
            tree.xinclude()
            for node in tree.findall("//Client"):
                print(node.attrib["name"])
        else:
            print("No command specified")
            raise SystemExit(1)
