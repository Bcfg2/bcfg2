import os
import sys
import BaseHTTPServer
import SimpleHTTPServer
import daemon
import Bcfg2.Server.Admin
import Bcfg2.Options

# For debugging output only
import logging
logger = logging.getLogger('Bcfg2.Server.Admin.Web')

class Web(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = "A simple webserver to display the content of the Bcfg2 repos."
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin web start\n"
                                    "\n\nbcfg2-admin web stop")
    __usage__ = ("bcfg2-admin web [start|stop]")

    def __init__(self, configfile):
        Bcfg2.Server.Admin.Mode.__init__(self, configfile)

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        opts = {'repo': Bcfg2.Options.SERVER_REPOSITORY}
        setup = Bcfg2.Options.OptionParser(opts)
        setup.parse(sys.argv[1:])
        repo = setup['repo']

        if len(args) == 0 or args[0] == '-h':
            print(self.__usage__)
            raise SystemExit(0)

        if len(args) == 0:
            self.errExit("No argument specified.\n"
                         "Please see bcfg2-admin web help for usage.")

        if args[0] in ['start', 'up']:
            # Change directory to the Bcfg2 repo
            if not os.path.exists(repo):
                #print "Path '%s' doesn't exisit" % repo
                logger.error("%s doesn't exist" % repo)
            else:
                os.chdir(repo)
                self.start_web()

        elif args[0] in ['stop', 'down']:
            self.stop_web()

        else:
            print "No command specified"
            raise SystemExit(1)

    # The web server part with hardcoded port number
    def start_web(self, port=6788):
        """Starts the webserver for directory listing of the Bcfg2 repo."""
        try:
            server_class  = BaseHTTPServer.HTTPServer
            handler_class = SimpleHTTPServer.SimpleHTTPRequestHandler
            server_address = ('', port)
            server = server_class(server_address, handler_class)
            #server.serve_forever()
            # Make the context manager for becoming a daemon process
            daemon_context = daemon.DaemonContext()
            daemon_context.files_preserve = [server.fileno()]

            # Become a daemon process
            with daemon_context:
                server.serve_forever()
        except:
            logger.error("Failed to start webserver")
            #raise Bcfg2.Server.Admin.AdminInitError

    def stop_web(self):
        """Stops the webserver."""
#        self.shutdown = 1
        self.shutdown()
 #       self.stopped = True
#        self.serve_forever()

