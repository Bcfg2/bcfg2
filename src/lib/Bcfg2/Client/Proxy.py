import os.path
import re
import sys
import time
import socket
import logging
import Bcfg2.Options
from Bcfg2.Compat import httplib, xmlrpclib, urlparse, quote_plus

# The ssl module is provided by either Python 2.6 or a separate ssl
# package that works on older versions of Python (see
# http://pypi.python.org/pypi/ssl).  If neither can be found, look for
# M2Crypto instead.
try:
    import ssl
    SSL_ERROR = ssl.SSLError
except ImportError:
    raise Exception("No SSL module support")


version = sys.version_info[:2]
has_py26 = version >= (2, 6)
has_py32 = version >= (3, 2)
has_py36 = version >= (3, 6)

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

    def __init__(self, host, port=None, strict=None, timeout=90, key=None,
                 cert=None, ca=None, scns=None, protocol='xmlrpc/tlsv1'):
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
            for details.  Required if using client certificate
            authentication.
        cert : string, optional
            The file system path to the local endpoint's SSL
            certificate.  May specify the same file as `cert` if using
            a file that contains both.  See
            http://docs.python.org/library/ssl.html#ssl-certificates
            for details.  Required if using client certificate
            authentication.
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
        self.logger = logging.getLogger("%s.%s" % (self.__class__.__module__,
                                                   self.__class__.__name__))
        self.key = key
        self.cert = cert
        self.ca = ca
        self.scns = scns
        self.protocol = protocol
        self.timeout = timeout

    def connect(self):
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
        elif self.protocol == 'xmlrpc/tls':
            if has_py36:
                ssl_protocol_ver = ssl.PROTOCOL_TLS
            else:
                self.logger.warning("Cannot use PROTOCOL_TLS, due to "
                                    "python version. Switching to "
                                    "PROTOCOL_TLSv1.")
                ssl_protocol_ver = ssl.PROTOCOL_TLSv1
        else:
            self.logger.error("Unknown protocol %s" % (self.protocol))
            raise Exception("unknown protocol %s" % self.protocol)
        if self.ca:
            other_side_required = ssl.CERT_REQUIRED
            if not os.path.isfile(self.ca):
                self.logger.error("CA specified but none found at %s" % self.ca)
        else:
            other_side_required = ssl.CERT_NONE
            self.logger.warning("No ca is specified. Cannot authenticate the "
                                "server with SSL.")
        if self.cert and not self.key:
            self.logger.warning("SSL cert specfied, but no key. Cannot "
                                "authenticate this client with SSL.")
            self.cert = None
        if self.key and not self.cert:
            self.logger.warning("SSL key specfied, but no cert. Cannot "
                                "authenticate this client with SSL.")
            self.key = None

        rawsock.settimeout(self.timeout)
        self.sock = ssl.wrap_socket(rawsock, cert_reqs=other_side_required,
                                  ca_certs=self.ca, suppress_ragged_eofs=True,
                                  keyfile=self.key, certfile=self.cert,
                                  ssl_version=ssl_protocol_ver)
        self.sock.connect((self.host, self.port))
        peer_cert = self.sock.getpeercert()
        if peer_cert and self.scns:
            scn = [x[0][1] for x in peer_cert['subject']
                   if x[0][0] == 'commonName'][0]
            if scn not in self.scns:
                raise CertificateError(scn)
        self.sock.closeSocket = True


class XMLRPCTransport(xmlrpclib.Transport):
    def __init__(self, key=None, cert=None, ca=None,
                 scns=None, use_datetime=0, timeout=90,
                 protocol='xmlrpc/tlsv1'):
        if hasattr(xmlrpclib.Transport, '__init__'):
            xmlrpclib.Transport.__init__(self, use_datetime)
        self.key = key
        self.cert = cert
        self.ca = ca
        self.scns = scns
        self.timeout = timeout
        self.protocol = protocol

    def make_connection(self, host):
        host, self._extra_headers = self.get_host_info(host)[0:2]
        return SSLHTTPConnection(host,
                                 key=self.key,
                                 cert=self.cert,
                                 ca=self.ca,
                                 scns=self.scns,
                                 timeout=self.timeout,
                                 protocol=self.protocol)

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


class ComponentProxy(xmlrpclib.ServerProxy):
    """Constructs proxies to components. """

    options = [
        Bcfg2.Options.Common.location, Bcfg2.Options.Common.ssl_ca,
        Bcfg2.Options.Common.password, Bcfg2.Options.Common.client_timeout,
        Bcfg2.Options.Common.protocol,
        Bcfg2.Options.PathOption(
            '--ssl-key', cf=('communication', 'key'), dest="key",
            help='Path to SSL key'),
        Bcfg2.Options.PathOption(
            cf=('communication', 'certificate'), dest="cert",
            help='Path to SSL certificate'),
        Bcfg2.Options.Option(
            "-u", "--user", default="root", cf=('communication', 'user'),
            help='The user to provide for authentication'),
        Bcfg2.Options.Option(
            "-R", "--retries", type=int, default=3,
            cf=('communication', 'retries'),
            help='The number of times to retry network communication'),
        Bcfg2.Options.Option(
            "-y", "--retry-delay", type=int, default=1,
            cf=('communication', 'retry_delay'),
            help='The time in seconds to wait between retries'),
        Bcfg2.Options.Option(
            '--ssl-cns', cf=('communication', 'serverCommonNames'),
            dest="ssl_cns",
            type=Bcfg2.Options.Types.colon_list,
            help='List of server commonNames')]

    def __init__(self):
        RetryMethod.max_retries = Bcfg2.Options.setup.retries
        RetryMethod.retry_delay = Bcfg2.Options.setup.retry_delay

        if Bcfg2.Options.setup.user and Bcfg2.Options.setup.password:
            method, path = urlparse(Bcfg2.Options.setup.server)[:2]
            url = "%s://%s:%s@%s" % (
                method,
                quote_plus(Bcfg2.Options.setup.user, ''),
                quote_plus(Bcfg2.Options.setup.password, ''),
                path)
        else:
            url = Bcfg2.Options.setup.server
        ssl_trans = XMLRPCTransport(
            key=Bcfg2.Options.setup.key,
            cert=Bcfg2.Options.setup.cert,
            ca=Bcfg2.Options.setup.ca,
            scns=Bcfg2.Options.setup.ssl_cns,
            timeout=Bcfg2.Options.setup.client_timeout,
            protocol=Bcfg2.Options.setup.protocol)
        xmlrpclib.ServerProxy.__init__(self, url,
                                       allow_none=True, transport=ssl_trans)
