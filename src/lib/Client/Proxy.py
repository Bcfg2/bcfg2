'''Cobalt proxy provides client access to cobalt components'''
__revision__ = '$Revision$'

import logging, socket, time, xmlrpclib, ConfigParser, httplib, OpenSSL

class CobaltComponentError(Exception):
    '''This error signals component connection errors'''
    pass

def verify_cb(conn, cert, errnum, depth, ok):
    print 'Got certificate: %s' % cert.get_subject()
    return ok

class poSSLFile:
    def __init__(self, sock, master):
        self.sock = sock
        self.master = master
        self.read = self.sock.read
        self.master.count += 1

    def close(self):
        self.master.count -= 1
        if not self.master.count:
            self.sock.close()

    def readline(self):
        data = ''
        char = self.read(1)
        while char != '\n':
            data += char
            char = self.read(1)
        print data
        return data

    def read(self, size=None):
        print "in read"
        if size:
            data = ''
            while not data:
                try:
                    data = self.sock.read(size)
                except ZeroReturnError:
                    print "caught ssl error; retrying"
            return data

class pSockMaster:
    def __init__(self, connection):
        self._connection = connection
        self.sendall = self._connection.send
        self.count = 1

    def makefile(self, mode, bufsize=None):
        return poSSLFile(self._connection, self)

    def close(self):
        self.count -= 1
        if not self.count:
            self._connection.close()
            
class PHTTPSConnection(httplib.HTTPSConnection):
    "This class allows communication via SSL."

    def __init__(self, host, port=None, key_file=None, cert_file=None,
                 strict=None):
        httplib.HTTPSConnection.__init__(self, host, port, strict)
        self.ctx = OpenSSL.SSL.Context(OpenSSL.SSL.SSLv23_METHOD)
        self.ctx.set_verify(OpenSSL.SSL.VERIFY_PEER, verify_cb)
        self.ctx.use_privatekey_file ('/tmp/keys/client.pkey')
        self.ctx.use_certificate_file('/tmp/keys/client.cert')
        self.ctx.load_verify_locations('/tmp/keys/CA.cert')

    def connect(self):
        "Connect to a host on a given (SSL) port."
        self._sock = OpenSSL.SSL.Connection(self.ctx,
                                           socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        self._sock.connect((self.host, self.port))
        self.sock = pSockMaster(self._sock)

class PHTTPS(httplib.HTTPS):
    _connection_class = PHTTPSConnection

class SafeTransport(xmlrpclib.Transport):
    """Handles an HTTPS transaction to an XML-RPC server."""
    def make_connection(self, host):
        # create a HTTPS connection object from a host descriptor
        # host may be a string, or a (host, x509-dict) tuple
        host, extra_headers, x509 = self.get_host_info(host)
        return PHTTPS(host, None, '/tmp/keys/client.pkey', '/tmp/keys/client.cert')

    def _parse_response(self, file, sock):
        # read response from input file/socket, and parse it

        p, u = self.getparser()

        while 1:
            if sock:
                response = sock.recv(1024)
            else:
                try:
                    response = file.read(1024)
                except OpenSSL.SSL.ZeroReturnError:
                    break
            if not response:
                break
            if self.verbose:
                print "body:", repr(response)
            p.feed(response)

        file.close()
        p.close()

        return u.close()

class SafeProxy:
    '''Wrapper for proxy'''
    _cfile = ConfigParser.ConfigParser()
    _cfpath = '/etc/bcfg2.conf'
    _cfile.read([_cfpath])
    try:
        _components = _cfile._sections['components']
    except KeyError:
        print "cobalt.conf doesn't contain a valid components section"
        raise SystemExit, 1
    try:
        _authinfo = ('root', _cfile.get('communication', 'password'))
    except KeyError:
        print "cobalt.conf doesn't contain a valid communication setup"
        raise SystemExit, 1
    _retries = 4

    def __init__(self, component, url=None):
        self.component = component
        self.log = logging.getLogger(component)
        if url != None:
            address = url
        else:
            address = self.__get_location(component)
        try:
            self.proxy = xmlrpclib.ServerProxy(address, transport=SafeTransport())
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
            except socket.sslerror:
                self.log.debug("Attempt %d of %d failed due to SSL negotiation failure" %
                               ((irs + 1), self._retries))
            except socket.error, serr:
                self.log.debug("Attempting %s (%d of %d) failed because %s" % (methodName, (irs+1),
                                                                               self._retries, serr))
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
