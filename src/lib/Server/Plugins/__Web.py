import os
import BaseHTTPServer
import SimpleHTTPServer
import Bcfg2.Server.Plugin

# for debugging output only
import logging
logger = logging.getLogger('Bcfg2.Plugins.Web')

class Web(Bcfg2.Server.Plugin.Plugin,
          Bcfg2.Server.Plugin.Version):
    """Web is a simple webserver to display the content of the Bcfg2 repos."""
    name = 'Web'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    experimental = True

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Version.__init__(self)
        self.core = core
        self.datastore = datastore

        # Change directory to the Bcfg2 repo
        ##path = '/home/fab/backup'
        if not os.path.exists(datastore):
            ##print "Path '%s' doesn't exisit" % datastore
            logger.error("%s doesn't exist" % datastore)
            raise Bcfg2.Server.Plugin.PluginInitError
        else:
            os.chdir(datastore)
            self.start_web()

        logger.debug("Serving at port %s" % port)


    def start_web(self, port=6788):
        """Starts the webserver for directory listing of the Bcfg2 repo."""
        try:
            server_class  = BaseHTTPServer.HTTPServer
            handler_class = SimpleHTTPServer.SimpleHTTPRequestHandler
            server_address = ('', port)
            server = server_class(server_address, handler_class)
            server.serve_forever()
        except:
            logger.error("Failed to start webserver")
            raise Bcfg2.Server.Plugin.PluginInitError
