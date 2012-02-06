import Bcfg2.Server.Plugin

class PackagesConfig(Bcfg2.Server.Plugin.SimpleConfig):
    _required = False
    
    def Index(self):
        """ Build local data structures """
        Bcfg2.Server.Plugin.SimpleConfig.Index(self)

        if hasattr(self.plugin, "sources") and self.plugin.sources.loaded:
            # only reload Packages plugin if sources have been loaded.
            # otherwise, this is getting called on server startup, and
            # we have to wait until all sources have been indexed
            # before we can call Packages.Reload()
            self.plugin.Reload()
