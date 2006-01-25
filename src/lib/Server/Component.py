'''Cobalt component base classes'''
__revision__ = '$Revision$'

from M2Crypto import SSL

import cPickle, logging, socket, urlparse, xmlrpclib, ConfigParser, SimpleXMLRPCServer

class CobaltXMLRPCRequestHandler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    '''CobaltXMLRPCRequestHandler takes care of ssl xmlrpc requests'''
    def __init__(self, request, client_address, server):
        SimpleXMLRPCServer.SimpleXMLRPCRequestHandler.__init__(self,
                                                               request, client_address, server)
        self.logger = logging.getLogger('Bcfg2.Server.Handler')
    
    def finish(self):
        '''Finish HTTPS connections properly'''
        self.request.set_shutdown(SSL.SSL_RECEIVED_SHUTDOWN | SSL.SSL_SENT_SHUTDOWN)
        self.request.close()

    def do_POST(self):
        '''Overload do_POST to pass through client address information'''
        try:
            # get arguments
            data = self.rfile.read(int(self.headers["content-length"]))
            response = self.server._cobalt_marshalled_dispatch(data, self.client_address)
        except: # This should only happen if the module is buggy
            # internal error, report as HTTP server error
            self.logger.error("Unexpected failure in handler", exc_info=1)
            self.send_response(500)
            self.end_headers()
        else:
            # got a valid XML RPC response
            self.send_response(200)
            self.send_header("Content-type", "text/xml")
            self.send_header("Content-length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

            # shut down the connection
            self.wfile.flush()
            self.connection.shutdown(1)

class Component(SSL.SSLServer,
                SimpleXMLRPCServer.SimpleXMLRPCDispatcher):
    """Cobalt component providing XML-RPC access"""
    __name__ = 'Component'
    __implementation__ = 'Generic'
    __statefields__ = []

    def __init__(self, setup):
        # need to get addr
        self.setup = setup
        self.cfile = ConfigParser.ConfigParser()
        self.logger = logging.getLogger('Bcfg2.Server')
        if setup['configfile']:
            cfilename = setup['configfile']
        else:
            cfilename = '/etc/cobalt.conf'
        self.cfile.read([cfilename])
        if not self.cfile.has_section('communication'):
            print "Configfile missing communication section"
            raise SystemExit, 1
        self.static = False
        if not self.cfile.has_section('components'):
            print "Configfile missing components section"
            raise SystemExit, 1
        
        if self.cfile._sections['components'].has_key(self.__name__):
            self.static = True
            location = urlparse.urlparse(self.cfile.get('components', self.__name__))[1].split(':')
            location = (location[0], int(location[1]))
        else:
            location = (socket.gethostname(), 0)

        self.password = self.cfile.get('communication', 'password')
        sslctx = SSL.Context('sslv23')
        try:
            keyfile = self.cfile.get('communication', 'key')
        except ConfigParser.NoOptionError:
            print "No key specified in cobalt.conf"
            raise SystemExit, 1
        sslctx.load_cert_chain(keyfile)
        #sslctx.load_verify_locations('ca.pem')
        #sslctx.set_client_CA_list_from_file('ca.pem')    
        sslctx.set_verify(SSL.verify_none, 15)
        #sslctx.set_allow_unknown_ca(1)
        sslctx.set_session_id_ctx(self.__name__)
        sslctx.set_info_callback(self.handle_sslinfo)
        #sslctx.set_tmp_dh('dh1024.pem')
        self.logRequests = 0
        # setup unhandled request syslog handling
        SimpleXMLRPCServer.SimpleXMLRPCDispatcher.__init__(self)
        SSL.SSLServer.__init__(self, location, CobaltXMLRPCRequestHandler, sslctx)
        self.port = self.socket.socket.getsockname()[1]
        self.logger.info("Bound to port %s" % self.port)
        self.funcs.update({'HandleEvents':self.HandleEvents,
                           'system.listMethods':self.system_listMethods})

    def HandleEvents(self, address, event_list):
        '''Default event handler'''
        return True

    def handle_sslinfo(self, where, ret, ssl_ptr):
        '''This is where we need to handle all ssl negotiation issues'''
        pass

    def _cobalt_marshalled_dispatch(self, data, address):
        """Decode and dispatch XMLRPC requests. Overloaded to pass through
        client address information
        """
        rawparams, method = xmlrpclib.loads(data)
        if len(rawparams) < 2:
            self.logger.error("No authentication included with request from %s" % address[0])
            return xmlrpclib.dumps(xmlrpclib.Fault(2, "No Authentication Info"))
        user = rawparams[0]
        password = rawparams[1]
        params = rawparams[2:]
        # check authentication
        if not self._authenticate_connection(method, user, password, address):
            self.logger.error("Authentication failure from %s" % address[0])
            return xmlrpclib.dumps(xmlrpclib.Fault(3, "Authentication Failure"))
        # generate response
        try:
            # all handlers must take address as the first argument
            response = self._dispatch(method, (address, ) + params)
            # wrap response in a singleton tuple
            response = (response,)
            response = xmlrpclib.dumps(response, methodresponse=1)
        except xmlrpclib.Fault, fault:
            response = xmlrpclib.dumps(fault)
        except TypeError, terror:
            self.logger.error("Client %s called function %s with wrong argument count" %
                   (address[0], method))
            response = xmlrpclib.dumps(xmlrpclib.Fault(4, terror.args[0]))
        except:
            self.logger.error("Unexpected failure in handler", exc_info=1)
            # report exception back to server
            response = xmlrpclib.dumps(xmlrpclib.Fault(1, "handler failure"))
        return response

    def _authenticate_connection(self, method, user, password, address):
        '''Authenticate new connection'''
        (user, address, method)
        return password == self.password

    def save_state(self):
        '''Save fields defined in __statefields__ in /var/spool/cobalt/__implementation__'''
        if self.__statefields__:
            savedata = tuple([getattr(self, field) for field in self.__statefields__])
        try:
            statefile = open("/var/spool/cobalt/%s" % self.__implementation__, 'w')
            # need to flock here
            statefile.write(cPickle.dumps(savedata))
        except:
            self.logger.info("Statefile save failed; data persistence disabled")
            self.__statefields__ = []

    def load_state(self):
        '''Load fields defined in __statefields__ from /var/spool/cobalt/__implementation__'''
        if self.__statefields__:
            try:
                loaddata = cPickle.loads(open("/var/spool/cobalt/%s" % self.__implementation__).read())
            except:
                self.logger.info("Statefile load failed")
                return
            for field in self.__statefields__:
                setattr(self, field, loaddata[self.__statefields__.index(field)])
                
    def system_listMethods(self, address):
        """get rid of the address argument and call the underlying dispatcher method"""
        return SimpleXMLRPCServer.SimpleXMLRPCDispatcher.system_listMethods(self)
