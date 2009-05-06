"""RPC client access to cobalt components.

Classes:
ComponentProxy -- an RPC client proxy to Cobalt components

Functions:
load_config -- read configuration files
"""

__revision__ = '$Revision: $'


from xmlrpclib import _Method

import httplib
import logging
import socket
import ssl
import time
import urlparse
import xmlrpclib

__all__ = ["ComponentProxy", "RetryMethod", "SSLHTTPConnection", "XMLRPCTransport"]

class RetryMethod(_Method):
    """Method with error handling and retries built in"""
    log = logging.getLogger('xmlrpc')
    def __call__(self, *args):
        max_retries = 4
        for retry in range(max_retries):
            try:
                return _Method.__call__(self, *args)
            except xmlrpclib.ProtocolError, err:
                self.log.error("Server failure: Protocol Error: %s %s" % \
                              (err.errcode, err.errmsg))
                raise xmlrpclib.Fault(20, "Server Failure")
            except xmlrpclib.Fault:
                raise
            except socket.error, err:
                if retry == 3:
                    self.log.error("Server failure: %s" % err)
                    raise xmlrpclib.Fault(20, err)
            except:
                self.log.error("Unknown failure", exc_info=1)
                break
            time.sleep(0.5)
        raise xmlrpclib.Fault(20, "Server Failure")

# sorry jon
xmlrpclib._Method = RetryMethod

class SSLHTTPConnection(httplib.HTTPConnection):
    def connect(self):
        rawsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rawsock.settimeout(90)
        self.sock = ssl.SSLSocket(rawsock, do_handshake_on_connect=False,
                                  suppress_ragged_eofs=True)
        self.sock.connect((self.host, self.port))
        self.sock.do_handshake()
        self.sock.closeSocket = True


class XMLRPCTransport(xmlrpclib.Transport):
    def make_connection(self, host):
        host = self.get_host_info(host)[0]
        http = SSLHTTPConnection(host)
        https = httplib.HTTP()
        https._setup(http)
        return https

def ComponentProxy (url, user=None, password=None, fingerprint=None,
                    key=None, cert=None):
    
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
    ssl_trans = XMLRPCTransport()
    return xmlrpclib.ServerProxy(newurl, allow_none=True, transport=ssl_trans)

