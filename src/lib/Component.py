'''Cobalt component base classes'''
__revision__ = '$Revision$'

import logging, select, signal, socket, sys, urlparse, xmlrpclib, cPickle, os
from base64 import decodestring

import BaseHTTPServer, SimpleXMLRPCServer
import Bcfg2.tlslite.errors
import Bcfg2.tlslite.api
from Bcfg2.tlslite.TLSConnection import TLSConnection

log = logging.getLogger('Component')

class ComponentInitError(Exception):
    '''Raised in case of component initialization failure'''
    pass

class ComponentKeyError(Exception):
    '''raised in case of key parse fails'''
    pass

class ForkedChild(Exception):
    '''raised after child has been forked'''
    pass

class CobaltXMLRPCRequestHandler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    '''CobaltXMLRPCRequestHandler takes care of ssl xmlrpc requests'''
    masterpid = os.getpid()

    def do_POST(self):
        '''Overload do_POST to pass through client address information'''
        try:
            # get arguments
            data = self.rfile.read(int(self.headers["content-length"]))

            authenticated = False
            #try x509 cert auth (will have been completed, just checking status)
            authenticated = self.request.authenticated
            #TLSConnection can be accessed by self.request?
            
            #try httpauth
            if not authenticated and "Authorization" in self.headers:
                binauth = self.headers['Authorization'].replace("Basic ", "")
                namepass = decodestring(binauth).split(':')
                if self.server._authenticate_connection("bogus-method",
                                                        namepass[0],
                                                        namepass[1],
                                                        self.client_address):
                    authenticated = True

            response = self.server._cobalt_marshalled_dispatch(data, self.client_address, authenticated)
        except ForkedChild:
            self.cleanup = False
            return
        except: # This should only happen if the module is buggy
            # internal error, report as HTTP server error
            log.error("Unexcepted handler failure in do_POST", exc_info=1)
            self.send_response(500)
            self.end_headers()
        else:
            # got a valid XML RPC response
            if os.getpid() != self.masterpid:
                pid = os.fork()
                if pid:
                    self.cleanup = False
                    return
            try:
                self.send_response(200)
                self.send_header("Content-type", "text/xml")
                self.send_header("Content-length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)
                
                # shut down the connection
                self.wfile.flush()
                #self.connection.shutdown()
            except socket.error:
                pass

    def setup(self):
        '''Setup a working connection'''
        self.cleanup = True
        self.connection = self.request
        self.rfile = socket._fileobject(self.request, "rb", self.rbufsize)
        self.wfile = socket._fileobject(self.request, "wb", self.wbufsize)

class TLSServer(Bcfg2.tlslite.api.TLSSocketServerMixIn,
                BaseHTTPServer.HTTPServer):
    '''This class is an tlslite-using SSLServer'''
    def __init__(self, address, keyfile, handler, checker=None,
                 reqCert=False):
        self.sc = Bcfg2.tlslite.api.SessionCache()
        self.rc = reqCert
        self.master = os.getpid()
        x509 = Bcfg2.tlslite.api.X509()
        s = open(keyfile).read()
        x509.parse(s)
        self.checker = checker
        try:
            self.key = Bcfg2.tlslite.api.parsePEMKey(s, private=True)
        except:
            raise ComponentKeyError
        self.chain = Bcfg2.tlslite.api.X509CertChain([x509])
        BaseHTTPServer.HTTPServer.__init__(self, address, handler)

    def finish_request(self, sock, address):
        sock.settimeout(90)
        tlsConnection = TLSConnection(sock)
        if self.handshake(tlsConnection) == True:
            req = self.RequestHandlerClass(tlsConnection, address, self)
            if req.cleanup:
                tlsConnection.close()
            if os.getpid() != self.master:
                os._exit(0)

    def handshake(self, tlsConnection):
        try:
            tlsConnection.handshakeServer(certChain=self.chain,
                                          privateKey=self.key,
                                          sessionCache=self.sc,
                                          checker=self.checker,
                                          reqCert=self.rc)
            tlsConnection.ignoreAbruptClose = True
            #Connection authenticated during TLS handshake, no need for passwords
            if not self.checker == None:
                tlsConnection.authenticated = True
            else:
                tlsConnection.authenticated = False
            return True
        except Bcfg2.tlslite.errors.TLSError, error:
            return False
        except socket.error:
            return False
                
class Component(TLSServer,
                SimpleXMLRPCServer.SimpleXMLRPCDispatcher):
    """Cobalt component providing XML-RPC access"""
    __name__ = 'Component'
    __implementation__ = 'Generic'
    __statefields__ = []
    async_funcs = []
    fork_funcs = []
    child_limit = 32

    def __init__(self, keyfile, password, location):
        # need to get addr
        self.shut = False
        signal.signal(signal.SIGINT, self.start_shutdown)
        signal.signal(signal.SIGTERM, self.start_shutdown)
        self.logger = logging.getLogger('Component')
        self.children = []
        self.static = True
        uparsed = urlparse.urlparse(location)[1].split(':')
        sock_loc = (uparsed[0], int(uparsed[1]))

        self.password = password

        try:
            TLSServer.__init__(self, sock_loc, keyfile, CobaltXMLRPCRequestHandler)
        except socket.error:
            self.logger.error("Failed to bind to socket")
            raise ComponentInitError
        except ComponentKeyError:
            self.logger.error("Failed to parse key" % (keyfile))
            raise ComponentInitError
        except:
            self.logger.error("Failed to load ssl key '%s'" % (keyfile), exc_info=1)
            raise ComponentInitError
        try:
            SimpleXMLRPCServer.SimpleXMLRPCDispatcher.__init__(self)
        except TypeError:
            SimpleXMLRPCServer.SimpleXMLRPCDispatcher.__init__(self, False, None)
        self.logRequests = 0
        self.port = self.socket.getsockname()[1]
        self.url = "https://%s:%s" % (socket.gethostname(), self.port)
        self.logger.info("Bound to port %s" % self.port)
        self.funcs.update({'system.listMethods':self.addr_system_listMethods})
        self.atime = 0

    def _cobalt_marshalled_dispatch(self, data, address, authenticated=False):
        """Decode and dispatch XMLRPC requests. Overloaded to pass through
        client address information
        """
        try:
            rawparams, method = xmlrpclib.loads(data)
        except:
            self.logger.error("Failed to parse request from %s" \
                              % (address[0]))
            #open('/tmp/badreq', 'w').write(data)
            return xmlrpclib.dumps(xmlrpclib.Fault(4, "Bad Request"))
        if not authenticated:
            if len(rawparams) < 2:
                self.logger.error("No authentication included with request from %s" % address[0])
                return xmlrpclib.dumps(xmlrpclib.Fault(2, "No Authentication Info"))
            user = rawparams[0]
            password = rawparams[1]
            params = rawparams[2:]
            # check authentication
            if not self._authenticate_connection(method, user, password, address):
                return xmlrpclib.dumps(xmlrpclib.Fault(3, "Authentication Failure"))
        else:
            #there is no prefixed auth info in this case
            params = rawparams[0:]
        # generate response
        try:
            # need to add waitpid code here to enforce maxchild
            if method in self.fork_funcs:
                self.clean_up_children()
                pid = os.fork()
                if pid:
                    self.children.append(pid)
                    raise ForkedChild
            # all handlers must take address as the first argument
            response = self._dispatch(method, (address, ) + params)
            # wrap response in a singleton tuple
            response = (response,)
            response = xmlrpclib.dumps(response, methodresponse=1)
        except xmlrpclib.Fault, fault:
            response = xmlrpclib.dumps(fault)
        except TypeError, terror:
            self.logger.error("Client %s called function %s with wrong argument count" %
                           (address[0], method), exc_info=1)
            response = xmlrpclib.dumps(xmlrpclib.Fault(4, terror.args[0]))
        except ForkedChild:
            raise
        except:
            self.logger.error("Unexpected handler failure", exc_info=1)
            # report exception back to server
            response = xmlrpclib.dumps(xmlrpclib.Fault(1,
                                   "%s:%s" % (sys.exc_type, sys.exc_value)))
        return response

    def clean_up_children(self):
        while True:
            try:
                pid = os.waitpid(0, os.WNOHANG)[0]
                if pid:
                    if pid in self.children:
                        self.children.remove(pid)
                else:
                    break
            except OSError:
                break
        if len(self.children) >= self.child_limit:
            self.logger.info("Reached child_limit; waiting for child exit")
            pid = os.waitpid(0, 0)[0]
            self.children.remove(pid)
            self.logger.debug("process %d exited" % pid)

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
                
    def addr_system_listMethods(self, address):
        """get rid of the address argument and call the underlying dispatcher method"""
        return SimpleXMLRPCServer.SimpleXMLRPCDispatcher.system_listMethods(self)

    def get_request(self):
        '''We need to do work between requests, so select with timeout instead of blocking in accept'''
        rsockinfo = []
        while self.socket not in rsockinfo:
            if self.shut:
                raise socket.error
            for funcname in self.async_funcs:
                func = getattr(self, funcname, False)
                if callable(func):
                    func()
                else:
                    self.logger.error("Cannot call uncallable method %s" % (funcname))
            try:
                rsockinfo = select.select([self.socket], [], [], 10)[0]
            except select.error:
                continue
            if self.socket in rsockinfo:
                return self.socket.accept()

    def serve_forever(self):
        """Handle one request at a time until doomsday."""
        while not self.shut:
            self.handle_request()

    def start_shutdown(self, signum, frame):
        '''Shutdown on unexpected signals'''
        self.shut = True

