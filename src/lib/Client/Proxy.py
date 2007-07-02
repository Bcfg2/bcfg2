'''Cobalt proxy provides client access to cobalt components'''
__revision__ = '$Revision$'

import logging, socket, time, xmlrpclib, ConfigParser, httplib
from Bcfg2.tlslite.integration.XMLRPCTransport import XMLRPCTransport
from Bcfg2.tlslite.integration.HTTPTLSConnection import HTTPTLSConnection
from Bcfg2.tlslite.TLSConnection import TLSConnection
import Bcfg2.tlslite.errors

#FIXME need to reimplement _binadaddress support for XMLRPCTransport

class MyHTTPTLSConnection(HTTPTLSConnection):
    def connect(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(sock, 'settimeout'):
            sock.settimeout(90)
        sock.connect((self.host, self.port))

        #Use a TLSConnection to emulate a socket
        self.sock = TLSConnection(sock)

        #When httplib closes this, close the socket
        self.sock.closeSocket = True
        self._handshake(self.sock)

class MyXMLRPCTransport(XMLRPCTransport):
    def make_connection(self, host):
        # create a HTTPS connection object from a host descriptor
        host, extra_headers, x509 = self.get_host_info(host)
        http = MyHTTPTLSConnection(host, None,
                                   self.username, self.password,
                                   self.sharedKey,
                                   self.certChain, self.privateKey,
                                   self.checker.cryptoID,
                                   self.checker.protocol,
                                   self.checker.x509Fingerprint,
                                   self.checker.x509TrustList,
                                   self.checker.x509CommonName,
                                   self.settings)
        http2 = httplib.HTTP()
        http2._setup(http)
        return http2

class CobaltComponentError(Exception):
    pass

class SafeProxy:
    '''Wrapper for proxy'''

    _retries = 4
    _authinfo = ()
    _components = {}
    def __init__(self, component, args={}):
        self.component = component
        self.log = logging.getLogger(component)

        if args.has_key('server'):
            # processing from command line args
            self._components[component] = args['server']
        else:
            if args.has_key('setup'):
                # processing from specified config file
                _cfpath = args['setup']
            else:
                _cfpath = '/etc/bcfg2.conf'
            self._cfile = ConfigParser.ConfigParser()
            self._cfile.read([_cfpath])
            try:
                self._components = self._cfile._sections['components']
            except:
                self.log.error("%s doesn't contain a valid components section" % (_cfpath))
                raise SystemExit, 1
        if args.has_key('password'):
            # get passwd from cmdline
            password = args['password']
        else:
            try:
                password = self._cfile.get('communication', 'password')
            except:
                self.log.error("%s doesn't contain a valid password" % (_cfpath))
                raise SystemExit, 1
        if args.has_key('user'):
            user = args['user']
        else:
            try:
                user = self._cfile.get('communication', 'user')
            except:
                user = 'root'
            
        self._authinfo = (user, password)

        if args.has_key('fingerprint'):
            self.fingerprint = args['fingerprint']
        else:
            self.fingerprint = False

        _bindaddress = ""
        try:
            _bindaddress = self._cfile.get('communication', 'bindaddress')
        except:
            pass
        
        if args.has_key('server'):
            address = args['server']
        else:
            address = self.__get_location(component)
            
        try:
            #             if _bindaddress != "":
            #                 self.log.info("Binding client to address %s" % _bindaddress)
            #                 self.proxy = xmlrpclib.ServerProxy(address, transport=Bcfg2SafeTransport())
            #             else:
            if self.fingerprint:
                transport = MyXMLRPCTransport(x509Fingerprint=self.fingerprint)
            else:
                transport = MyXMLRPCTransport()
            self.proxy = xmlrpclib.ServerProxy(address, transport=transport)

        except IOError, io_error:
            self.log.error("Invalid server URL %s: %s" % (address, io_error))
            raise CobaltComponentError
        except:
            self.log.error("Failed to initialize xml-rpc", exc_info=1)

    def run_method(self, methodName, methodArgs):
        ''' Perform an XMLRPC invocation against the server'''
        method = getattr(self.proxy, methodName)
        for irs in range(self._retries):
            try:
                ret = apply(method, self._authinfo + methodArgs)
                if irs > 0:
                    self.log.warning("Required %d attempts to contact %s for operation %s" %
                                     (irs, self.component, methodName))
                self.log.debug("%s completed successfully" % (methodName))
                return ret
            except xmlrpclib.ProtocolError:
                self.log.error("Server failure: Protocol Error")
                raise xmlrpclib.Fault(20, "Server Failure")
            except xmlrpclib.Fault:
                self.log.debug("Operation %s completed with fault" % (methodName))
                raise
            except socket.error, serr:
                self.log.debug("Attempting %s (%d of %d) failed because %s" % (methodName, (irs+1),
                                                                               self._retries, serr))
            except Bcfg2.tlslite.errors.TLSFingerprintError, err:
                self.log.error("Server fingerprint did not match")
                errmsg = err.message.split()
                self.log.error("Got %s expected %s" % (errmsg[3], errmsg[4]))
                raise SystemExit, 1
            except:
                self.log.error("Unknown failure", exc_info=1)
                break
            time.sleep(0.5)
        self.log.error("%s failed:\nCould not connect to %s" % (methodName, self.component))
        raise xmlrpclib.Fault(20, "Server Failure")
        
    def __get_location(self, name):
        '''Perform component location lookups if needed'''
        if self._components.has_key(name):
            return self._components[name]
        slp = SafeProxy('service-location', url=self._cfile.get('components', 'service-location'))
        try:
            sdata = slp.run_method('LookupService',
                                   ([{'tag':'location', 'name':name, 'url':'*'}],))
        except xmlrpclib.Fault:
            raise CobaltComponentError, "No Such Component"
        if sdata:
            curl = sdata[0]['url']
            self._components[name] = curl
            return curl

    def dummy(self):
        '''dummy method for pylint'''
        return True
            
class ComponentProxy(SafeProxy):
    '''Component Proxy instantiates a SafeProxy to a component and registers local functions
    based on its definition'''
    name = 'dummy'
    methods = []

    def __init__(self, url=None):
        SafeProxy.__init__(self, self.name, url)
        for method in self.methods:
            setattr(self, method, eval('lambda *x:self.run_method(method, x)',
                                       {'self':self, 'method':method}))

class service_location(ComponentProxy):
    '''service-location component-specific proxy'''
    name = 'service-location'
    methods = ['AssertService', 'LookupService', 'DeassertService']

class allocation_manager(ComponentProxy):
    '''allocation manager specific component proxy'''
    name = 'allocation-manager'
    methods = ['GetProject']

class file_stager(ComponentProxy):
    '''File staging component'''
    name = 'file-stager'
    methods = ['StageInit', 'FinalizeStage']

class process_manager(ComponentProxy):
    '''process manager specific component proxy'''
    name = 'process-manager'
    methods = ['CreateProcessGroup', 'GetProcessGroup', 'KillProcessGroup', 'WaitProcessGroup']

class queue_manager(ComponentProxy):
    '''queue manager proxy'''
    name = 'queue-manager'
    methods = ['AddJob', 'GetJobs', 'DelJobs', 'RunJobs', 'SetJobs', 'SetJobID']

class scheduler(ComponentProxy):
    '''scheduler proxy'''
    name = 'scheduler'
    methods = ['AddReservation', 'DelReservation', 'GetPartition', 'AddPartition', 'DelPartition', 'Set']

class bcfg2(ComponentProxy):
    '''bcfg2 client code'''
    name = 'bcfg2'
    methods = ['AssertProfile', 'GetConfig', 'GetProbes', 'RecvProbeData', 'RecvStats']

class CommDict(dict):
    '''CommDict is a dictionary that automatically instantiates a component proxy upon access'''
    commnames = {'pm':process_manager, 'fs':file_stager, 'am':allocation_manager,
                 'sched':scheduler, 'qm':queue_manager}

    def __getitem__(self, name):
        if not self.has_key(name):
            self.__setitem__(name, self.commnames[name]())
        return dict.__getitem__(self, name)
