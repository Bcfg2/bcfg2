import os
import logging
from Bcfg2.Bcfg2Py3k import ConfigParser
from Bcfg2.Server.Plugins.Packages import *

logger = logging.getLogger('Packages')

class PackagesConfig(Bcfg2.Server.Plugin.FileBacked,
                     ConfigParser.SafeConfigParser):
    def __init__(self, filename, fam, packages):
        Bcfg2.Server.Plugin.FileBacked.__init__(self, filename)
        ConfigParser.SafeConfigParser.__init__(self)

        self.fam = fam
        # packages.conf isn't strictly necessary, so only set a
        # monitor if it exists. if it gets added, that will require a
        # server restart
        if os.path.exists(self.name):
            self.fam.AddMonitor(self.name, self)

        self.pkg_obj = packages

    def Index(self):
        """ Build local data structures """
        for section in self.sections():
            self.remove_section(section)
        self.read(self.name)
        if self.pkg_obj.sources.loaded:
            # only reload Packages plugin if sources have been loaded.
            # otherwise, this is getting called on server startup, and
            # we have to wait until all sources have been indexed
            # before we can call Packages.Reload()
            self.pkg_obj.Reload()
