import dulwich
import time
import tarfile
from subprocess import Popen
import Bcfg2.Server.Admin
from Bcfg2.Server.Plugins.Metadata import MetadataConsistencyError

class Examples(Bcfg2.Server.Admin.MetadataCore):
    __shorthelp__ = "Pulls in the data from the Bcfg2 sample repository"
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin examples pull\n"
                                    "\n\nbcfg2-admin examples update\n"
                                    "bcfg2-admin examples backup")
    __usage__ = ("bcfg2-admin examples [options] [add|del|update|list] [attr=val]")

    def __init__(self, configfile):
        Bcfg2.Server.Admin.MetadataCore.__init__(self, configfile,
                                                 self.__usage__)

    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)


        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Version.__init__(self)
        self.core = core
        self.datastore = datastore

        if len(args) == 0:
            self.errExit("No argument specified.\n"
                         "Please see bcfg2-admin examples help for usage.")

        if args[0] == 'pull':
            try:
            # FIXME: Repo URL is hardcoded for now
                Popen(['git', 'clone', 'https://github.com/solj/bcfg2-repo.git', datastore])
            except MetadataConsistencyError:
                print "Error in pulling examples."
                raise SystemExit(1)

#fatal: destination path 'bcfg2-test' already exists and is not an empty directory.

        elif args[0] == 'backup':
            try:
                self.metadata.add_group(args[1], attr_d)
            except MetadataConsistencyError:
                print "Error in adding group"
                raise SystemExit(1)


        elif args[0] == 'backup':
            try:
                self.metadata.add_group(args[1], attr_d)
            except MetadataConsistencyError:
                print "Error in adding group"
                raise SystemExit(1)

        else:
            print "No command specified"
            raise SystemExit(1)

    def repobackup():
        """Make a backup of the existing files in the Bcfg2 repo directory."""
        if os.path.isdir(datastore):
            print 'Backup in progress...'
            target = time.strftime('%Y%m%d%H%M%S')
            
            
             out = tarfile.open(filename, w.gz)            
        else:
            logger.error("%s doesn't exist." % datastore)
            #raise Bcfg2.Server.Plugin.PluginInitError
