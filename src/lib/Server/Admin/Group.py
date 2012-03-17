import lxml.etree
import Bcfg2.Server.Admin
from Bcfg2.Server.Plugins.Metadata import MetadataConsistencyError
from Bcfg2.metargs import Option
import Bcfg2.Options


class Group(Bcfg2.Server.Admin.MetadataCore):
    __shorthelp__ = "Create, delete, or modify group entries"
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin group add <group> "
                                    "attr1=val1 attr2=val2"
                                    "\nbcfg2-admin group update <group> "
                                    "attr1=val1 attr2=val2"
                                    "\nbcfg2-admin group list"
                                    "\nbcfg2-admin group del <group>\n")
    __usage__ = ("bcfg2-admin group [options] [add|del|update|list] [attr=val]")

    def __init__(self):
        Bcfg2.Server.Admin.MetadataCore.__init__(self)
        Bcfg2.Options.set_help(self.__shorthelp__)
        Bcfg2.Options.add_options(
            Option('command', help='Action to execute',
                   choices=['add', 'update', 'up', 'delete', 'remove',
                            'del', 'rm', 'list', 'ls'])
        )

        def split_attr(val):
            return val.split('=', 1)

        args = Bcfg2.Options.bootstrap()
        
        if args.command not in ['list', 'ls']:
            Bcfg2.Options.add_options(
                Option('group', help='Group to update'),
                Option('attributes', help='Attributes to update', metavar='attr=val',
                       nargs='*', type=split_attr)
            )

    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)
        if args.command == 'add':
            attr_d = {}
            for attr, val in args.attributes:
                if attr not in ['profile', 'public', 'default',
                               'name', 'auth', 'toolset', 'category',
                               'comment']:
                    print("Attribute %s unknown" % attr)
                    raise SystemExit(1)
                attr_d[attr] = val
            try:
                self.metadata.add_group(args.group, attr_d)
            except MetadataConsistencyError:
                print("Error in adding group")
                raise SystemExit(1)
        elif args.command in ['update', 'up']:
            attr_d = {}
            for attr, val in args.attributes:
                if attr not in ['profile', 'public', 'default',
                                'name', 'auth', 'toolset', 'category',
                                'comment']:
                    print("Attribute %s unknown" % attr)
                    raise SystemExit(1)
                attr_d[attr] = val
            try:
                self.metadata.update_group(args.group, attr_d)
            except MetadataConsistencyError:
                print("Error in updating group")
                raise SystemExit(1)
        elif args.command in ['delete', 'remove', 'del', 'rm']:
            try:
                self.metadata.remove_group(args.group)
            except MetadataConsistencyError:
                print("Error in deleting group")
                raise SystemExit(1)
        elif args.command in ['list', 'ls']:
            tree = lxml.etree.parse(self.metadata.data + "/groups.xml")
            for node in tree.findall("//Group"):
                print(node.attrib["name"])
        else:
            print("No command specified")
            raise SystemExit(1)
