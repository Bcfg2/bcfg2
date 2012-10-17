""" Make a backup of the Bcfg2 repository """

import os
import time
import tarfile
import Bcfg2.Server.Admin
import Bcfg2.Options


class Backup(Bcfg2.Server.Admin.MetadataCore):
    """ Make a backup of the Bcfg2 repository """

    def __call__(self, args):
        datastore = self.setup['repo']
        timestamp = time.strftime('%Y%m%d%H%M%S')
        fmt = 'gz'
        mode = 'w:' + fmt
        filename = timestamp + '.tar' + '.' + fmt
        out = tarfile.open(os.path.join(datastore, filename), mode=mode)
        out.add(datastore, os.path.basename(datastore))
        out.close()
        print("Archive %s was stored under %s" % (filename, datastore))
