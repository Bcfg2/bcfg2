""" DBstats provides a database-backed statistics handler """

import Bcfg2.Server.Plugin


class DBStats(Bcfg2.Server.Plugin.Plugin):
    """ DBstats provides a database-backed statistics handler """

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        self.logger.error("DBStats has been replaced with Reporting")
        self.logger.error("DBStats: Be sure to migrate your data "
                          "before running the report collector")
        raise Bcfg2.Server.Plugin.PluginInitError
