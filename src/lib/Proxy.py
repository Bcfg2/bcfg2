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

__all__ = ["ComponentProxy", "RetryMethod"]

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
            except socket.error, (err, msg):
                if retry == 3:
                    self.log.error("Server failure: %s" % msg)
                    raise xmlrpclib.Fault(20, msg)
            except Bcfg2.tlslite.errors.TLSFingerprintError, err:
                raise
            except Bcfg2.tlslite.errors.TLSError, err:
                self.log.error("Unexpected TLS Error: %s. Retrying" % \
                               (err.message))
            except:
                self.log.error("Unknown failure", exc_info=1)
                break
            time.sleep(0.5)
        raise xmlrpclib.Fault(20, "Server Failure")

# sorry jon
xmlrpclib._Method = RetryMethod

def ComponentProxy (url, user=None, password=None, fingerprint=None):
    
    """Constructs proxies to components.
    
    Arguments:
    component_name -- name of the component to connect to
    
    Additional arguments are passed to the ServerProxy constructor.
    """
    
    if user and password:
        method, path = urlparse.urlparse(url)[:2]
        newurl = "%s://%s:%s@%s" % (method, user, password, path)
    else:
        newurl = url
    return xmlrpclib.ServerProxy(newurl, allow_none=True,
                                 transport=XMLRPCTransport(x509Fingerprint=fingerprint))

