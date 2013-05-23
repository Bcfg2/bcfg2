import re
import socket
import logging

# The ssl module is provided by either Python 2.6 or a separate ssl
# package that works on older versions of Python (see
# http://pypi.python.org/pypi/ssl).  If neither can be found, look for
# M2Crypto instead.
try:
    import ssl
    SSL_LIB = 'py26_ssl'
    SSL_ERROR = ssl.SSLError
except ImportError:
    from M2Crypto import SSL
    import M2Crypto.SSL.Checker
    SSL_LIB = 'm2crypto'
    SSL_ERROR = SSL.SSLError

import sys
import time

# Compatibility imports
from Bcfg2.Compat import httplib, xmlrpclib, urlparse, quote_plus

version = sys.version_info[:2]
has_py26 = version >= (2, 6)
has_py32 = version >= (3, 2)

__all__ = ["ComponentProxy",
           "RetryMethod",
           "SSLHTTPConnection",
           "XMLRPCTransport"]


class ProxyError(Exception):
    """ ProxyError provides a consistent reporting interface to
    the various xmlrpclib errors that might arise (mainly
    ProtocolError and Fault) """
    def __init__(self, err):
        msg = None
        if isinstance(err, xmlrpclib.ProtocolError):
            # cut out the password in the URL
            url = re.sub(r'([^:]+):(.*?)@([^@]+:\d+/)', r'\1:******@\3',
                         err.url)
            msg = "XML-RPC Protocol Error for %s: %s (%s)" % (url,
                                                              err.errmsg,
                                                              err.errcode)
        elif isinstance(err, xmlrpclib.Fault):
            msg = "XML-RPC Fault: %s (%s)" % (err.faultString,
                                              err.faultCode)
        else:
            msg = str(err)
        Exception.__init__(self, msg)


class CertificateError(Exception):
    def __init__(self, commonName):
        self.commonName = commonName

    def __str__(self):
        return ("Got unallowed commonName %s from server"
                % self.commonName)


_orig_Method = xmlrpclib._Method

class RetryMethod(xmlrpclib._Method):
    """Method with error handling and retries built in."""
    log = logging.getLogger('xmlrpc')
    max_retries = 3
    retry_delay = 1

    def __call__(self, *args):
        for retry in range(self.max_retries):
            if retry >= self.max_retries - 1:
                final = True
            else:
                final = False
            msg = None
            try:
                return _orig_Method.__call__(self, *args)
            except xmlrpclib.ProtocolError:
                err = sys.exc_info()[1]
                msg = "Server failure: Protocol Error: %s %s" % \
                    (err.errcode, err.errmsg)
            except xmlrpclib.Fault:
                msg = sys.exc_info()[1]
            except socket.error:
                err = sys.exc_info()[1]
                if hasattr(err, 'errno') and err.errno == 336265218:
                    msg = "SSL Key error: %s" % err
                elif hasattr(err, 'errno') and err.errno == 185090050:
                    msg = "SSL CA error: %s" % err
                elif final:
                    msg = "Server failure: %s" % err
            except CertificateError:
                err = sys.exc_info()[1]
                msg = "Got unallowed commonName %s from server" % \
                    err.commonName
            except KeyError:
                err = sys.exc_info()[1]
                msg = "Server disallowed connection: %s" % err
            except ProxyError:
                err = sys.exc_info()[1]
                msg = err
            except:
                raise
                etype, err = sys.exc_info()[:2]
                msg = "Unknown failure: %s (%s)" % (err, etype.__name__)
            if msg:
                if final:
                    self.log.error(msg)
                    raise ProxyError(msg)
                else:
                    self.log.info(msg)
                    time.sleep(self.retry_delay)

xmlrpclib._Method = RetryMethod


class SSLHTTPConnection(httplib.HTTPConnection):
    """Extension of HTTPConnection that
    implements SSL and related behaviors.
    """

    logger = logging.getLogger('Bcfg2.Proxy.SSLHTTPConnection')

    def __init__(self, host, port=None, strict=None, timeout=90, key=None,
                 cert=None, ca=None, scns=None, protocol='xmlrpc/ssl'):
        """Initializes the `httplib.HTTPConnection` object and stores security
        parameters

        Parameters
        ----------
        host : string
            Name of host to contact
        port : int, optional
            Port on which to contact the host.  If none is specified,
            the default port of 80 will be used unless the `host`
            string has a port embedded in the form host:port.
        strict : Boolean, optional
            Passed to the `httplib.HTTPConnection` constructor and if
            True, causes the `BadStatusLine` exception to be raised if
            the status line cannot be parsed as a valid HTTP 1.0 or
            1.1 status.
        timeout : int, optional
            Causes blocking operations to timeout after `timeout`
            seconds.
        key : string, optional
            The file system path to the local endpoint's SSL key.  May
            specify the same file as `cert` if using a file that
            contains both.  See
            http://docs.python.org/library/ssl.html#ssl-certificates
            for details.  Required if using xmlrpc/ssl with client
            certificate authentication.
        cert : string, optional
            The file system path to the local endpoint's SSL
            certificate.  May specify the same file as `cert` if using
            a file that contains both.  See
            http://docs.python.org/library/ssl.html#ssl-certificates
            for details.  Required if using xmlrpc/ssl with client
            certificate authentication.
        ca : string, optional
            The file system path to a set of concatenated certificate
            authority certs, which are used to validate certificates
            passed from the other end of the connection.
        scns : array-like, optional
            List of acceptable server commonNames.  The peer cert's
            common name must appear in this list, otherwise the
            connect() call will throw a `CertificateError`.
        protocol : {'xmlrpc/ssl', 'xmlrpc/tlsv1'}, optional
            Communication protocol to use.

        """
        if not has_py26:
            httplib.HTTPConnection.__init__(self, host, port, strict)
        elif not has_py32:
            httplib.HTTPConnection.__init__(self, host, port, strict, timeout)
        else:
            # the strict parameter is deprecated.
            # HTTP 0.9-style "Simple Responses" are not supported anymore.
            httplib.HTTPConnection.__init__(self, host, port, timeout=timeout)
        self.key = key
        self.cert = cert
        self.ca = ca
        self.scns = scns
        self.protocol = protocol
        self.timeout = timeout

    def connect(self):
        """Initiates a connection using previously set attributes."""
        if SSL_LIB == 'py26_ssl':
            self._connect_py26ssl()
        elif SSL_LIB == 'm2crypto':
            self._connect_m2crypto()
        else:
            raise Exception("No SSL module support")

    def _connect_py26ssl(self):
        """Initiates a connection using the ssl module."""
        # check for IPv6
        hostip = socket.getaddrinfo(self.host,
                                    self.port,
                                    socket.AF_UNSPEC,
                                    socket.SOCK_STREAM)[0][4][0]
        if ':' in hostip:
            rawsock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        else:
            rawsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if self.protocol == 'xmlrpc/ssl':
            ssl_protocol_ver = ssl.PROTOCOL_SSLv23
        elif self.protocol == 'xmlrpc/tlsv1':
            ssl_protocol_ver = ssl.PROTOCOL_TLSv1
        else:
            self.logger.error("Unknown protocol %s" % (self.protocol))
            raise Exception("unknown protocol %s" % self.protocol)
        if self.ca:
            other_side_required = ssl.CERT_REQUIRED
        else:
            other_side_required = ssl.CERT_NONE
            self.logger.warning("No ca is specified. Cannot authenticate the server with SSL.")
        if self.cert and not self.key:
            self.logger.warning("SSL cert specfied, but no key. Cannot authenticate this client with SSL.")
            self.cert = None
        if self.key and not self.cert:
            self.logger.warning("SSL key specfied, but no cert. Cannot authenticate this client with SSL.")
            self.key = None

        rawsock.settimeout(self.timeout)
        self.sock = ssl.SSLSocket(rawsock, cert_reqs=other_side_required,
                                  ca_certs=self.ca, suppress_ragged_eofs=True,
                                  keyfile=self.key, certfile=self.cert,
                                  ssl_version=ssl_protocol_ver)
        self.sock.connect((self.host, self.port))
        peer_cert = self.sock.getpeercert()
        if peer_cert and self.scns:
            scn = [x[0][1] for x in peer_cert['subject'] if x[0][0] == 'commonName'][0]
            if scn not in self.scns:
                raise CertificateError(scn)
        self.sock.closeSocket = True

    def _connect_m2crypto(self):
        """Initiates a connection using the M2Crypto module."""

        if self.protocol == 'xmlrpc/ssl':
            ctx = SSL.Context('sslv23')
        elif self.protocol == 'xmlrpc/tlsv1':
            ctx = SSL.Context('tlsv1')
        else:
            self.logger.error("Unknown protocol %s" % (self.protocol))
            raise Exception("unknown protocol %s" % self.protocol)

        if self.ca:
            # Use the certificate authority to validate the cert
            # presented by the server
            ctx.set_verify(SSL.verify_peer | SSL.verify_fail_if_no_peer_cert, depth=9)
            if ctx.load_verify_locations(self.ca) != 1:
                raise Exception('No CA certs')
        else:
            self.logger.warning("No ca is specified. Cannot authenticate the server with SSL.")

        if self.cert and self.key:
            # A cert/key is defined, use them to support client
            # authentication to the server
            ctx.load_cert(self.cert, self.key)
        elif self.cert:
            self.logger.warning("SSL cert specfied, but no key. Cannot authenticate this client with SSL.")
        elif self.key:
            self.logger.warning("SSL key specfied, but no cert. Cannot authenticate this client with SSL.")

        self.sock = SSL.Connection(ctx)
        if re.match('\\d+\\.\\d+\\.\\d+\\.\\d+', self.host):
            # host is ip address
            try:
                hostname = socket.gethostbyaddr(self.host)[0]
            except:
                # fall back to ip address
                hostname = self.host
        else:
            hostname = self.host
        try:
            self.sock.connect((hostname, self.port))
            # automatically checks cert matches host
        except M2Crypto.SSL.Checker.WrongHost:
            wr = sys.exc_info()[1]
            raise CertificateError(wr)


class XMLRPCTransport(xmlrpclib.Transport):
    def __init__(self, key=None, cert=None, ca=None,
                 scns=None, use_datetime=0, timeout=90):
        if hasattr(xmlrpclib.Transport, '__init__'):
            xmlrpclib.Transport.__init__(self, use_datetime)
        self.key = key
        self.cert = cert
        self.ca = ca
        self.scns = scns
        self.timeout = timeout

    def make_connection(self, host):
        host, self._extra_headers = self.get_host_info(host)[0:2]
        return SSLHTTPConnection(host,
                                 key=self.key,
                                 cert=self.cert,
                                 ca=self.ca,
                                 scns=self.scns,
                                 timeout=self.timeout)

    def request(self, host, handler, request_body, verbose=0):
        """Send request to server and return response."""
        try:
            conn = self.send_request(host, handler, request_body, False)
            response = conn.getresponse()
            errcode = response.status
            errmsg = response.reason
            headers = response.msg
        except (socket.error, SSL_ERROR, httplib.BadStatusLine):
            err = sys.exc_info()[1]
            raise ProxyError(xmlrpclib.ProtocolError(host + handler,
                                                     408,
                                                     str(err),
                                                     self._extra_headers))

        if errcode != 200:
            raise ProxyError(xmlrpclib.ProtocolError(host + handler,
                                                     errcode,
                                                     errmsg,
                                                     headers))

        self.verbose = verbose
        return self.parse_response(response)

    if sys.hexversion < 0x03000000:
        # pylint: disable=E1101
        def send_request(self, host, handler, request_body, debug):
            """ send_request() changed significantly in py3k."""
            conn = self.make_connection(host)
            xmlrpclib.Transport.send_request(self, conn, handler, request_body)
            self.send_host(conn, host)
            self.send_user_agent(conn)
            self.send_content(conn, request_body)
            return conn
        # pylint: enable=E1101


def ComponentProxy(url, user=None, password=None, key=None, cert=None, ca=None,
                   allowedServerCNs=None, timeout=90, retries=3, delay=1):

    """Constructs proxies to components.

    Arguments:
    component_name -- name of the component to connect to

    Additional arguments are passed to the ServerProxy constructor.

    """
    xmlrpclib._Method.max_retries = retries
    xmlrpclib._Method.retry_delay = delay

    if user and password:
        method, path = urlparse(url)[:2]
        newurl = "%s://%s:%s@%s" % (method, quote_plus(user, ''),
                                    quote_plus(password, ''), path)
    else:
        newurl = url
    ssl_trans = XMLRPCTransport(key, cert, ca,
                                allowedServerCNs, timeout=float(timeout))
    return xmlrpclib.ServerProxy(newurl, allow_none=True, transport=ssl_trans)
