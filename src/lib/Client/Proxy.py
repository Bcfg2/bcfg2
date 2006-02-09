'''Cobalt proxy provides client access to cobalt components'''
__revision__ = '$Revision:$'

import logging, socket, time, xmlrpclib, ConfigParser

class CobaltComponentError(Exception):
    '''This error signals component connection errors'''
    pass

class SafeProxy:
    '''Wrapper for proxy'''
    _cfile = ConfigParser.ConfigParser()
    _cfile.read(['/etc/cobalt.conf'])
    _components = _cfile._sections['components']
    _authinfo = ('root', _cfile.get('communication', 'password'))
    _retries = 4

    def __init__(self, component, url=None):
        self.component = component
        self.log = logging.getLogger(component)
        if url != None:
            address = url
        else:
            address = self.__get_location(component)
        try:
            self.proxy = xmlrpclib.ServerProxy(address)
        except IOError, io_error:
            self.log.error("Invalid server URL %s: %s" % (address, io_error))
            raise CobaltComponentError
        except:
            self.log.error("Failed to initialize xml-rpc", exc_info=1)

    def run_method(self, method_name, method_args):
        ''' Perform an XMLRPC invocation against the server'''
        method = getattr(self.proxy, method_name)
        for irs in range(self._retries):
            try:
                ret = apply(method, self._authinfo + method_args)
                if irs > 0:
                    self.log.warning("Required %d attempts to contact %s for operation %s" %
                                     (irs, self.component, method_name))
                self.log.debug("%s completed successfully" % (method_name))
                return ret
            except xmlrpclib.ProtocolError:
                self.log.error("Server failure: Protocol Error")
                raise xmlrpclib.Fault(20, "Server Failure")
            except xmlrpclib.Fault:
                self.log.debug("Operation %s completed with fault" % (method_name))
                raise
            except socket.error:
                self.log.debug("Attempting %s (%d of %d) failed" % (method_name, (irs+1), self._retries))
                time.sleep(0.5)                
            except:
                break
        self.log.error("%s failed:\nCould not connect to %s" % (method_name, self.component))
        
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

class process_manager(ComponentProxy):
    '''process manager specific component proxy'''
    name = 'process-manager'
    methods = ['CreateProcessGroup', 'GetProcessGroup']
