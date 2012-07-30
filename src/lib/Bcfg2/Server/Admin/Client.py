import lxml.etree
import Bcfg2.Server.Admin
from Bcfg2.Server.Plugins.Metadata import MetadataConsistencyError


class Client(Bcfg2.Server.Admin.MetadataCore):
    __shorthelp__ = "Create, delete, or list client entries"
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin client add <client> "
                                    "\nbcfg2-admin client list"
                                    "\nbcfg2-admin client del <client>\n")
    __usage__ = ("bcfg2-admin client [options] [add|del|list] [attr=val]")

    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)
        if len(args) == 0:
            self.errExit("No argument specified.\n"
                         "Usage: %s" % self.usage)
        if args[0] == 'add':
            try:
                self.metadata.add_client(args[1])
            except MetadataConsistencyError:
                print("Error in adding client")
                raise SystemExit(1)
        elif args[0] in ['delete', 'remove', 'del', 'rm']:
            try:
                self.metadata.remove_client(args[1])
            except MetadataConsistencyError:
                print("Error in deleting client")
                raise SystemExit(1)
        elif args[0] in ['list', 'ls']:
            for client in self.metadata.list_clients():
                print(client.hostname)
        else:
            print("No command specified")
            raise SystemExit(1)

