import os
import time
import tarfile
import Bcfg2.Server.Admin
import Bcfg2.Options


class Backup(Bcfg2.Server.Admin.MetadataCore):
    __shorthelp__ = "Make a backup of the Bcfg2 repository"
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin backup\n")
                                    #"\n\nbcfg2-admin backup restore")

    def __init__(self):
        Bcfg2.Server.Admin.MetadataCore.__init__(self)
        Bcfg2.Options.add_option(Bcfg2.Options.SERVER_REPOSITORY)
        Bcfg2.Options.set_help(self.__shorthelp__)

    def __call__(self, args):
        Bcfg2.Server.Admin.MetadataCore.__call__(self, args)
        # Get Bcfg2 repo directory
        self.datastore = args.repository_path
        timestamp = time.strftime('%Y%m%d%H%M%S')
        format = 'gz'
        mode = 'w:' + format
        filename = timestamp + '.tar' + '.' + format
        out = tarfile.open(self.datastore + '/' + filename, mode=mode)
        out.add(self.datastore, os.path.basename(self.datastore))
        out.close()
        print("Archive %s was stored under %s" % (filename, self.datastore))
