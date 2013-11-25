""" Create, delete, or list client entries """

import sys
import Bcfg2.Server.Admin
from Bcfg2.Server.Plugin import MetadataConsistencyError


def get_attribs(args):
    """ Get a list of attributes to set on a client when adding/updating it """
    attr_d = {}
    for i in args[2:]:
        attr, val = i.split('=', 1)
        if attr not in ['profile', 'uuid', 'password', 'floating', 'secure',
                        'address', 'auth']:
            print("Attribute %s unknown" % attr)
            raise SystemExit(1)
        attr_d[attr] = val
    return attr_d


class Client(Bcfg2.Server.Admin.MetadataCore):
    """ Create, delete, or list client entries """
    __usage__ = "[options] [add|del|update|list] [attr=val]"
    __plugin_whitelist__ = ["Metadata"]

    def __call__(self, args):
        if len(args) == 0:
            self.errExit("No argument specified.\n"
                         "Usage: %s" % self.__usage__)
        if args[0] == 'add':
            try:
                self.metadata.add_client(args[1], get_attribs(args))
            except MetadataConsistencyError:
                self.errExit("Error adding client: %s" % sys.exc_info()[1])
        elif args[0] in ['update', 'up']:
            try:
                self.metadata.update_client(args[1], get_attribs(args))
            except MetadataConsistencyError:
                self.errExit("Error updating client: %s" % sys.exc_info()[1])
        elif args[0] in ['delete', 'remove', 'del', 'rm']:
            try:
                self.metadata.remove_client(args[1])
            except MetadataConsistencyError:
                self.errExit("Error deleting client: %s" %
                             sys.exc_info()[1])
        elif args[0] in ['list', 'ls']:
            for client in self.metadata.list_clients():
                print(client)
        else:
            self.errExit("No command specified")
