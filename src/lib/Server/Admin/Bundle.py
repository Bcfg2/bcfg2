import Bcfg2.Server.Admin
from Bcfg2.Server.Plugins.Metadata import MetadataConsistencyError

class Bundle(Bcfg2.Server.Admin.MetadataCore):
    __shorthelp__ = "Create or delete bundle entries"
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin bundle add <bundle> "
                                    "bcfg2-admin bundle del <bundle>")
    __usage__ = ("bcfg2-admin bundle [options] [add|del] [group]")

    def __init__(self, configfile):
        Bcfg2.Server.Admin.MetadataCore.__init__(self, configfile,
                                                 self.__usage__)

    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)
        if len(args) == 0:
            self.errExit("No argument specified.\n"
                         "Please see bcfg2-admin bundle help for usage.")
        if args[0] == 'add':
            try:
                self.metadata.add_bundle(args[1])
            except MetadataConsistencyError:
                print "Error in adding bundle"
                raise SystemExit(1)
        elif args[0] in ['delete', 'remove', 'del', 'rm']:
            try:
                self.metadata.remove_bundle(args[1])
            except MetadataConsistencyError:
                print "Error in deleting bundle"
                raise SystemExit(1)
        else:
            print "No command specified"
            raise SystemExit(1)
