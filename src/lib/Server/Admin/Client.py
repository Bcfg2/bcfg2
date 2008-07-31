import Bcfg2.Server.Admin
from Bcfg2.Server.Plugins.Metadata import MetadataConsistencyError

class Client(Bcfg2.Server.Admin.MetadataCore):
    __shorthelp__ = 'bcfg2-admin client add <client> attr1=val1 attr2=val2\nbcfg2-admin client del <client>'
    __longhelp__ = __shorthelp__ + '\n\tCreate or delete client entries'
    def __init__(self, configfile):
        Bcfg2.Server.Admin.MetadataCore.__init__(self, configfile)

    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)
        if len(args) == 0:
            self.errExit("Client mode requires at least one argument: <add> or <delete>")
        if "-h" in args:
            print "Usage: "
            print self.__shorthelp__
            raise SystemExit(1)
	if args[0] == 'add':
            attr_d = {}
            for i in args[2:]:
                attr, val = i.split('=', 1)
                if attr not in ['profile', 'user', 'state', 'image',
                                'action']:
                    print "Attribute %s unknown" % attr
                    raise SystemExit(1)
                attr_d[attr] = val
            try:
                self.metadata.add_client(args[1], attr_d)
            except MetadataConsistencyError:
                print "Error in adding client"
                raise SystemExit(1)
        elif args[0] in ['delete', 'remove', 'del', 'rm']:
            try:
                self.metadata.remove_client(args[1])
            except MetadataConsistencyError:
                print "Error in deleting client"
                raise SystemExit(1)
        else:
            print "No command specified"
            raise SystemExit(1)
