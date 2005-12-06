'''Cobalt component base classes'''
__revision__ = '$Revision: 1.4 $'

from ConfigParser import ConfigParser, NoOptionError
from cPickle import loads, dumps
from M2Crypto import SSL
from SimpleXMLRPCServer import SimpleXMLRPCRequestHandler
from select import select
from socket import gethostname
from sys import exc_info
import sys
from syslog import openlog, syslog, LOG_INFO, LOG_ERR, LOG_LOCAL0
from traceback import extract_tb
from xmlrpclib import dumps, loads, Fault
from urlparse import urlparse

try:
    from SimpleXMLRPCServer import SimpleXMLRPCDispatcher
except ImportError:
    SimpleXMLRPCDispatcher = object

class CobaltXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):
    '''CobaltXMLRPCRequestHandler takes care of ssl xmlrpc requests'''
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
            (trace, val, trb) = exc_info()
            syslog(LOG_ERR, "Unexpected failure in handler")
            for line in extract_tb(trb):
                syslog(LOG_ERR, '  File "%s", line %i, in %s\n    %s\n' % line)
            syslog(LOG_ERR, "%s: %s\n"%(trace, val))
            del trace, val, trb
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
                SimpleXMLRPCDispatcher):
    """Cobalt component providing XML-RPC access"""
    __name__ = 'Component'
    __implementation__ = 'Generic'
    __statefields__ = []

    def __init__(self, setup):
        # need to get addr
        self.setup = setup
        self.cfile = ConfigParser()
        openlog(self.__implementation__, 0, LOG_LOCAL0)
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
            location = urlparse(self.cfile.get('components', self.__name__))[1].split(':')
            location = (location[0], int(location[1]))
        else:
            location = (gethostname(), 0)

        self.password = self.cfile.get('communication', 'password')
        sslctx = SSL.Context('sslv23')
        try:
            keyfile = self.cfile.get('communication', 'key')
        except NoOptionError:
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
        SimpleXMLRPCDispatcher.__init__(self)
        SSL.SSLServer.__init__(self, location, CobaltXMLRPCRequestHandler, sslctx)
        self.port = self.socket.socket.getsockname()[1]
        syslog(LOG_INFO, "Bound to port %s" % self.port)
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
        rawparams, method = loads(data)
        if len(rawparams) < 2:
            syslog(LOG_ERR, "No authentication included with request from %s" % address[0])
            return dumps(Fault(2, "No Authentication Info"))
        user = rawparams[0]
        password = rawparams[1]
        params = rawparams[2:]
        # check authentication
        if not self._authenticate_connection(method, user, password, address):
            syslog(LOG_ERR, "Authentication failure from %s" % address[0])
            return dumps(Fault(3, "Authentication Failure"))
        # generate response
        try:
            # all handlers must take address as the first argument
            response = self._dispatch(method, (address, ) + params)
            # wrap response in a singleton tuple
            response = (response,)
            response = dumps(response, methodresponse=1)
        except Fault, fault:
            response = dumps(fault)
        except TypeError, t:
            syslog(LOG_ERR, "Client %s called function %s with wrong argument count" %
                   (address[0], method))
            response = dumps(Fault(4, t.args[0]))
        except:
            (trace, val, trb) = exc_info()
            syslog(LOG_ERR, "Unexpected failure in handler")
            for line in extract_tb(trb):
                syslog(LOG_ERR, '  File "%s", line %i, in %s\n    %s\n' % line)
            syslog(LOG_ERR, "%s: %s\n"%(trace, val))
            del trace, val, trb
            # report exception back to server
            response = dumps(Fault(1,
                                   "%s:%s" % (sys.exc_type, sys.exc_value)))

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
            statefile.write(dumps(savedata))
        except:
            syslog(LOG_INFO, "Statefile save failed; data persistence disabled")
            self.__statefields__ = []

    def load_state(self):
        '''Load fields defined in __statefields__ from /var/spool/cobalt/__implementation__'''
        if self.__statefields__:
            try:
                loaddata = loads(open("/var/spool/cobalt/%s" % self.__implementation__).read())
            except:
                syslog(LOG_INFO, "Statefile load failed")
                return
            for field in self.__statefields__:
                setattr(self, field, loaddata[self.__statefields__.index(field)])
                
    def system_listMethods(self, address):
        """get rid of the address argument and call the underlying dispatcher method"""
        return SimpleXMLRPCDispatcher.system_listMethods(self)
