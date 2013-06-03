""" Create, delete, or list client entries """

import sys
import Bcfg2.Server.Admin
from Bcfg2.Server.Plugin import MetadataConsistencyError


class Client(Bcfg2.Server.Admin.MetadataCore):
    """ Create, delete, or list client entries """
    __usage__ = "[options] [add|del|list] [attr=val]"
    __plugin_whitelist__ = ["Metadata"]

    def __call__(self, args):
        if len(args) == 0:
            self.errExit("No argument specified.\n"
                         "Usage: %s" % self.__usage__)
        if args[0] == 'add':
            try:
                self.metadata.add_client(args[1])
            except MetadataConsistencyError:
                self.errExit("Error in adding client: %s" % sys.exc_info()[1])
        elif args[0] in ['delete', 'remove', 'del', 'rm']:
            try:
                self.metadata.remove_client(args[1])
            except MetadataConsistencyError:
                self.errExit("Error in deleting client: %s" %
                             sys.exc_info()[1])
        elif args[0] in ['list', 'ls']:
            for client in self.metadata.list_clients():
                print(client)
        else:
            self.errExit("No command specified")
