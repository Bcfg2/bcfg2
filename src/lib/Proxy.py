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
import string
import sys
import time
import urlparse
import xmlrpclib

version = string.split(string.split(sys.version)[0], ".")
has_py26 = map(int, version) >= [2, 6]

__all__ = ["ComponentProxy", "RetryMethod", "SSLHTTPConnection", "XMLRPCTransport"]

class CertificateError(Exception):
    def __init__(self, commonName):
        self.commonName = commonName

class RetryMethod(_Method):
    """Method with error handling and retries built in"""
    log = logging.getLogger('xmlrpc')
    max_retries = 4
    def __call__(self, *args):
        for retry in range(self.max_retries):
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
            except CertificateError, ce:
                self.log.error("Got unallowed commonName %s from server" \
                               % ce.commonName)
                break
            except:
                self.log.error("Unknown failure", exc_info=1)
                break
            time.sleep(0.5)
        raise xmlrpclib.Fault(20, "Server Failure")

# sorry jon
xmlrpclib._Method = RetryMethod

class SSLHTTPConnection(httplib.HTTPConnection):
    def __init__(self, host, port=None, strict=None, timeout=90, key=None,
                 cert=None, ca=None, scns=None, protocol='xmlrpc/ssl'):
        if not has_py26:
            httplib.HTTPConnection.__init__(self, host, port, strict)
        else:
            httplib.HTTPConnection.__init__(self, host, port, strict, timeout)
        self.key = key
        self.cert = cert
        self.ca = ca
        self.scns = scns
        if self.ca:
            self.ca_mode = ssl.CERT_REQUIRED
        else:
            self.ca_mode = ssl.CERT_NONE
        if protocol == 'xmlrpc/ssl':
            self.ssl_protocol = ssl.PROTOCOL_SSLv23
        elif protocol == 'xmlrpc/tlsv1':
            self.ssl_protocol = ssl.PROTOCOL_TLSv1
        else:
            self.logger.error("Unknown protocol %s" % (protocol))
            raise Exception, "unknown protocol %s" % protocol


    def connect(self):
        rawsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if has_py26:
            rawsock.settimeout(self.timeout)
        self.sock = ssl.SSLSocket(rawsock, cert_reqs=self.ca_mode,
                                  ca_certs=self.ca, suppress_ragged_eofs=True,
                                  keyfile=self.key, certfile=self.cert,
                                  ssl_version=self.ssl_protocol)
        self.sock.connect((self.host, self.port))
        pc = self.sock.getpeercert()
        if pc and self.scns:
            scn = [x[0][1] for x in pc['subject'] if x[0][0] == 'commonName'][0]
            if scn not in self.scns:
                raise CertificateError, scn
        self.sock.closeSocket = True


class XMLRPCTransport(xmlrpclib.Transport):
    def __init__(self, key=None, cert=None, ca=None, scns=None, use_datetime=0, timeout=90):
        if hasattr(xmlrpclib.Transport, '__init__'):
            xmlrpclib.Transport.__init__(self, use_datetime)
        self.key = key
        self.cert = cert
        self.ca = ca
        self.scns = scns
        self.timeout = timeout

    def make_connection(self, host):
        host = self.get_host_info(host)[0]
        http = SSLHTTPConnection(host, key=self.key, cert=self.cert, ca=self.ca,
                                 scns=self.scns, timeout=self.timeout)
        https = httplib.HTTP()
        https._setup(http)
        return https

    def request(self, host, handler, request_body, verbose=0):
        '''send request to server and return response'''
        h = self.make_connection(host)
        self.send_request(h, handler, request_body)
        self.send_host(h, host)
        self.send_user_agent(h)
        self.send_content(h, request_body)

        errcode, errmsg, headers = h.getreply()
        msglen = int(headers.dict['content-length'])

        if errcode != 200:
            raise xmlrpclib.ProtocolError(host + handler, errcode, errmsg, headers)

        self.verbose = verbose

        return self._get_response(h.getfile(), msglen)

    def _get_response(self, fd, length):
        # read response from input file/socket, and parse it
        recvd = 0

        p, u = self.getparser()

        while recvd < length:
            rlen = min(length - recvd, 1024)
            response = fd.read(rlen)
            recvd += len(response)
            if not response:
                break
            if self.verbose:
                print "body:", repr(response), len(response)
            p.feed(response)

        fd.close()
        p.close()

        return u.close()

def ComponentProxy (url, user=None, password=None, key=None, cert=None, ca=None,
                    allowedServerCNs=None, timeout=90):
    
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
    ssl_trans = XMLRPCTransport(key, cert, ca, allowedServerCNs, timeout=timeout)
    return xmlrpclib.ServerProxy(newurl, allow_none=True, transport=ssl_trans)

