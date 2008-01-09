"""RPC client access to cobalt components.

Classes:
ComponentProxy -- an RPC client proxy to Cobalt components

Functions:
load_config -- read configuration files
"""

__revision__ = '$Revision: $'

from ConfigParser import SafeConfigParser, NoSectionError
import logging, socket, urlparse, time, Bcfg2.tlslite.errors
from Bcfg2.tlslite.integration.XMLRPCTransport import XMLRPCTransport
import xmlrpclib
from xmlrpclib import _Method

__all__ = [
    "ComponentProxy", "ComponentLookupError", "RetryMethod", 
    "register_component", "find_configured_servers",
]

local_components = dict()
known_servers = dict()

def register_component (component):
    local_components[component.name] = component


class ComponentError (Exception):
    
    """Component error baseclass"""


class ComponentLookupError (ComponentError):

    """Unable to locate an address for the given component."""


class ComponentOperationError (ComponentError):
    
    """Component Failure during operation"""


class RetryMethod(_Method):
    """Method with error handling and retries built in"""
    log = logging.getLogger('xmlrpc')
    def __call__(self, *args):
        max_retries = 4
        for retry in range(max_retries):
            try:
                return _Method.__call__(self, *args)
            except xmlrpclib.ProtocolError:
                self.log.error("Server failure: Protocol Error")
                raise xmlrpclib.Fault(20, "Server Failure")
            except socket.error:
                pass
            except Bcfg2.tlslite.errors.TLSFingerprintError, err:
                self.log.error("Server fingerprint did not match")
                errmsg = err.message.split()
                self.log.error("Got %s expected %s" % (errmsg[3], errmsg[4]))
                raise SystemExit, 1
            except:
                self.log.error("Unknown failure", exc_info=1)
                break
            time.sleep(0.5)
        raise xmlrpclib.Fault(20, "Server Failure")

# sorry jon
xmlrpclib._Method = RetryMethod

def ComponentProxy (component_name, defer=False, user=None, password=None,
                    fingerprint=None):
    
    """Constructs proxies to components.
    
    Arguments:
    component_name -- name of the component to connect to
    
    Additional arguments are passed to the ServerProxy constructor.
    """
    
    if defer:
        return DeferredProxy(component_name)
    
    if component_name in local_components:
        return LocalProxy(local_components[component_name])
    elif component_name in known_servers:
        url = known_servers[component_name]
    elif component_name != "service-location":
        try:
            slp = ComponentProxy("service-location")
        except ComponentLookupError:
            raise ComponentLookupError(component_name)
        try:
            url = slp.locate(component_name)
        except:
            raise ComponentLookupError(component_name)
        if not url:
            raise ComponentLookupError(component_name)
    else:
        raise ComponentLookupError(component_name)
    # process url
    if user and password:
        method, path = urlparse.urlparse(url)[:2]
        newurl = "%s://%s:%s@%s" % (method, user, password, path)
    else:
        newurl = url
    return xmlrpclib.ServerProxy(newurl, allow_none=True,
                                 transport=XMLRPCTransport(x509Fingerprint=fingerprint))

class LocalProxy (object):
    
    """Proxy-like filter for inter-component communication.
    
    Used to access other components stored in local memory,
    without having to transport across tcp/http.
    
    Dispatches method calls through the component's _dispatch
    method to keep the interface between this and ServerProxy
    consistent.
    """
    
    def __init__ (self, component):
        self._component = component
    
    def __getattr__ (self, attribute):
        return LocalProxyMethod(self, attribute)


class LocalProxyMethod (object):
    
    def __init__ (self, proxy, func_name):
        self._proxy = proxy
        self._func_name = func_name
    
    def __call__ (self, *args):
        return self._proxy._component._dispatch(self._func_name, args)


class DeferredProxy (object):
    
    """Defering proxy object.
    
    Gets a new proxy when it can't connect to a component.
    """
    
    def __init__ (self, component_name):
        self._component_name = component_name
    
    def __getattr__ (self, attribute):
        return DeferredProxyMethod(self, attribute)


class DeferredProxyMethod (object):
    
    def __init__ (self, proxy, func_name):
        self._proxy = proxy
        self._func_name = func_name
    
    def __call__ (self, *args):
        proxy = ComponentProxy(self._proxy._component_name, defer=False)
        func = getattr(proxy, self._func_name)
        return func(*args)


def find_configured_servers (config_files=None):
    """Read associated config files into the module.
    
    Arguments:
    config_files -- a list of paths to config files.
    """
    if not config_files:
        config_files = ['/etc/bcfg2.conf']
    config = SafeConfigParser()
    config.read(config_files)
    try:
        components = config.options("components")
    except NoSectionError:
        return []
    known_servers.clear()
    known_servers.update(dict([
        (component, config.get("components", component))
        for component in components
    ]))
    return known_servers.copy()

find_configured_servers()
