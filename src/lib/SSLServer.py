"""Bcfg2 SSL server."""

__revision__ = '$Revision$'

__all__ = [
    "SSLServer", "XMLRPCRequestHandler", "XMLRPCServer",
]

import os
import sys
import socket
import base64
import select
import signal
import logging
import ssl
import threading
import time
import types
# Compatibility imports
from Bcfg2.Bcfg2Py3k import xmlrpclib, SimpleXMLRPCServer, SocketServer


class ForkedChild(Exception):
    pass


class XMLRPCDispatcher (SimpleXMLRPCServer.SimpleXMLRPCDispatcher):
    logger = logging.getLogger("Cobalt.Server.XMLRPCDispatcher")

    def __init__(self, allow_none, encoding):
        try:
            SimpleXMLRPCServer.SimpleXMLRPCDispatcher.__init__(self,
                                                               allow_none,
                                                               encoding)
        except:
            # Python 2.4?
            SimpleXMLRPCServer.SimpleXMLRPCDispatcher.__init__(self)

        self.allow_none = allow_none
        self.encoding = encoding

    def _marshaled_dispatch(self, address, data):
        method_func = None
        params, method = xmlrpclib.loads(data)
        try:
            if '.' not in method:
                params = (address, ) + params
            response = self.instance._dispatch(method, params, self.funcs)
            # py3k compatibility
            if type(response) not in [bool, str, list, dict, types.NoneType]:
                response = (response.decode('utf-8'), )
            else:
                response = (response, )
            raw_response = xmlrpclib.dumps(response, methodresponse=1,
                                           allow_none=self.allow_none,
                                           encoding=self.encoding)
        except xmlrpclib.Fault:
            fault = sys.exc_info()[1]
            raw_response = xmlrpclib.dumps(fault,
                                           allow_none=self.allow_none,
                                           encoding=self.encoding)
        except:
            self.logger.error("Unexpected handler error", exc_info=1)
            # report exception back to server
            raw_response = xmlrpclib.dumps(
                xmlrpclib.Fault(1, "%s:%s" % (sys.exc_type, sys.exc_value)),
                allow_none=self.allow_none, encoding=self.encoding)
        return raw_response


class SSLServer (SocketServer.TCPServer, object):

    """TCP server supporting SSL encryption.

    Methods:
    handshake -- perform a SSL/TLS handshake

    Properties:
    url -- A url pointing to this server.

    """

    allow_reuse_address = True
    logger = logging.getLogger("Cobalt.Server.TCPServer")

    def __init__(self, listen_all, server_address, RequestHandlerClass,
                 keyfile=None, certfile=None, reqCert=False, ca=None,
                 timeout=None, protocol='xmlrpc/ssl'):

        """Initialize the SSL-TCP server.

        Arguments:
        server_address -- address to bind to the server
        RequestHandlerClass -- class to handle requests

        Keyword arguments:
        keyfile -- private encryption key filename (enables ssl encryption)
        certfile -- certificate file (enables ssl encryption)
        reqCert -- client must present certificate
        timeout -- timeout for non-blocking request handling

        """

        if listen_all:
            listen_address = ('', server_address[1])
        else:
            listen_address = (server_address[0], server_address[1])
        try:
            SocketServer.TCPServer.__init__(self, listen_address,
                                            RequestHandlerClass)
        except socket.error:
            self.logger.error("Failed to bind to socket")
            raise

        self.timeout = timeout
        self.socket.settimeout(timeout)
        self.keyfile = keyfile
        if keyfile != None:
            if keyfile == False or not os.path.exists(keyfile):
                self.logger.error("Keyfile %s does not exist" % keyfile)
                raise Exception("keyfile doesn't exist")
        self.certfile = certfile
        if certfile != None:
            if certfile == False or not os.path.exists(certfile):
                self.logger.error("Certfile %s does not exist" % certfile)
                raise Exception("certfile doesn't exist")
        self.ca = ca
        if ca != None:
            if ca == False or not os.path.exists(ca):
                self.logger.error("CA %s does not exist" % ca)
                raise Exception("ca doesn't exist")
        self.reqCert = reqCert
        if ca and certfile:
            self.mode = ssl.CERT_OPTIONAL
        else:
            self.mode = ssl.CERT_NONE
        if protocol == 'xmlrpc/ssl':
            self.ssl_protocol = ssl.PROTOCOL_SSLv23
        elif protocol == 'xmlrpc/tlsv1':
            self.ssl_protocol = ssl.PROTOCOL_TLSv1
        else:
            self.logger.error("Unknown protocol %s" % (protocol))
            raise Exception("unknown protocol %s" % protocol)

    def get_request(self):
        (sock, sockinfo) = self.socket.accept()
        sock.settimeout(self.timeout)
        sslsock = ssl.wrap_socket(sock,
                                  server_side=True,
                                  certfile=self.certfile,
                                  keyfile=self.keyfile,
                                  cert_reqs=self.mode,
                                  ca_certs=self.ca,
                                  ssl_version=self.ssl_protocol)
        return sslsock, sockinfo

    def close_request(self, request):
        try:
            request.unwrap()
        except:
            pass
        try:
            request.close()
        except:
            pass

    def _get_url(self):
        port = self.socket.getsockname()[1]
        hostname = socket.gethostname()
        protocol = "https"
        return "%s://%s:%i" % (protocol, hostname, port)
    url = property(_get_url)


class XMLRPCRequestHandler (SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):

    """Component XML-RPC request handler.

    Adds support for HTTP authentication.

    Exceptions:
    CouldNotAuthenticate -- client did not present acceptable authentication information

    Methods:
    authenticate -- prompt a check of a client's provided username and password
    handle_one_request -- handle a single rpc (optionally authenticating)

    """
    logger = logging.getLogger("Cobalt.Server.XMLRPCRequestHandler")

    def authenticate(self):
        try:
            header = self.headers['Authorization']
        except KeyError:
            self.logger.error("No authentication data presented")
            return False
        auth_type, auth_content = header.split()
        try:
            # py3k compatibility
            auth_content = base64.standard_b64decode(auth_content)
        except TypeError:
            auth_content = base64.standard_b64decode(bytes(auth_content.encode('ascii')))
        try:
            # py3k compatibility
            try:
                username, password = auth_content.split(":")
            except TypeError:
                username, pw = auth_content.split(bytes(":", encoding='utf-8'))
                password = pw.decode('utf-8')
        except ValueError:
            username = auth_content
            password = ""
        cert = self.request.getpeercert()
        client_address = self.request.getpeername()
        return self.server.instance.authenticate(cert, username,
                                                 password, client_address)

    def parse_request(self):
        """Extends parse_request.

        Optionally check HTTP authentication when parsing.

        """
        if not SimpleXMLRPCServer.SimpleXMLRPCRequestHandler.parse_request(self):
            return False
        try:
            if not self.authenticate():
                self.logger.error("Authentication Failure")
                self.send_error(401, self.responses[401][0])
                return False
        except:
            self.logger.error("Unexpected Authentication Failure", exc_info=1)
            self.send_error(401, self.responses[401][0])
            return False
        return True

    ### need to override do_POST here
    def do_POST(self):
        try:
            max_chunk_size = 10 * 1024 * 1024
            size_remaining = int(self.headers["content-length"])
            L = []
            while size_remaining:
                try:
                    select.select([self.rfile.fileno()], [], [], 3)
                except select.error:
                    print("got select timeout")
                    raise
                chunk_size = min(size_remaining, max_chunk_size)
                L.append(self.rfile.read(chunk_size).decode('utf-8'))
                size_remaining -= len(L[-1])
            data = ''.join(L)
            response = self.server._marshaled_dispatch(self.client_address,
                                                       data)
            if sys.hexversion >= 0x03000000:
                response = response.encode('utf-8')
        except:
            try:
                self.send_response(500)
                self.end_headers()
            except:
                (type, msg) = sys.exc_info()[:2]
                self.logger.error("Error sending 500 response (%s): %s" % \
                    (type, msg))
                raise
        else:
            # got a valid XML RPC response
            try:
                self.send_response(200)
                self.send_header("Content-type", "text/xml")
                self.send_header("Content-length", str(len(response)))
                self.end_headers()
                failcount = 0
                while True:
                    try:
                        # If we hit SSL3_WRITE_PENDING here try to resend.
                        self.wfile.write(response)
                        break
                    except ssl.SSLError:
                        e = sys.exc_info()[1]
                        if str(e).find("SSL3_WRITE_PENDING") < 0:
                            raise
                        self.logger.error("SSL3_WRITE_PENDING")
                        failcount += 1
                        if failcount < 5:
                            continue
                        raise
            except:
                (type, msg) = sys.exc_info()[:2]
                if str(type) == 'socket.error' and msg[0] == 32:
                    self.logger.warning("Connection dropped from %s" %
                                        self.client_address[0])
                elif str(type) == 'socket.error' and msg[0] == 104:
                    self.logger.warning("Connection reset by peer: %s" %
                                        self.client_address[0])
                elif str(type) == 'ssl.SSLError':
                    self.logger.warning("SSLError handling client %s: %s" %
                                        (self.client_address[0], msg))
                else:
                    self.logger.error("Error sending response (%s): %s" %
                                      (type, msg))

    def finish(self):
        # shut down the connection
        if not self.wfile.closed:
            try:
                self.wfile.flush()
                self.wfile.close()
            except socket.error:
                err = sys.exc_info()[1]
                self.logger.warning("Error closing connection: %s" % err)
        self.rfile.close()


class XMLRPCServer (SocketServer.ThreadingMixIn, SSLServer,
                    XMLRPCDispatcher, object):

    """Component XMLRPCServer.

    Methods:
    serve_daemon -- serve_forever in a daemonized process
    serve_forever -- handle_one_request until not self.serve
    shutdown -- stop serve_forever (by setting self.serve = False)
    ping -- return all arguments received

    RPC methods:
    ping

    (additional system.* methods are inherited from base dispatcher)

    Properties:
    require_auth -- the request handler is requiring authorization
    credentials -- valid credentials being used for authentication

    """

    def __init__(self, listen_all, server_address, RequestHandlerClass=None,
                 keyfile=None, certfile=None, ca=None, protocol='xmlrpc/ssl',
                 timeout=10,
                 logRequests=False,
                 register=True, allow_none=True, encoding=None):

        """Initialize the XML-RPC server.

        Arguments:
        server_address -- address to bind to the server
        RequestHandlerClass -- request handler used by TCP server (optional)

        Keyword arguments:
        keyfile -- private encryption key filename
        certfile -- certificate file
        logRequests -- log all requests (default False)
        register -- presence should be reported to service-location (default True)
        allow_none -- allow None values in xml-rpc
        encoding -- encoding to use for xml-rpc (default UTF-8)

        """

        XMLRPCDispatcher.__init__(self, allow_none, encoding)

        if not RequestHandlerClass:
            class RequestHandlerClass (XMLRPCRequestHandler):
                """A subclassed request handler to prevent class-attribute conflicts."""

        SSLServer.__init__(self,
                           listen_all,
                           server_address,
                           RequestHandlerClass,
                           ca=ca,
                           timeout=timeout,
                           keyfile=keyfile,
                           certfile=certfile,
                           protocol=protocol)
        self.logRequests = logRequests
        self.serve = False
        self.register = register
        self.register_introspection_functions()
        self.register_function(self.ping)
        self.logger.info("service available at %s" % self.url)
        self.timeout = timeout

    def _tasks_thread(self):
        try:
            while self.serve:
                try:
                    if self.instance and hasattr(self.instance, 'do_tasks'):
                        self.instance.do_tasks()
                except:
                    self.logger.error("Unexpected task failure", exc_info=1)
                time.sleep(self.timeout)
        except:
            self.logger.error("tasks_thread failed", exc_info=1)

    def server_close(self):
        SSLServer.server_close(self)
        self.logger.info("server_close()")

    def _get_require_auth(self):
        return getattr(self.RequestHandlerClass, "require_auth", False)

    def _set_require_auth(self, value):
        self.RequestHandlerClass.require_auth = value
    require_auth = property(_get_require_auth, _set_require_auth)

    def _get_credentials(self):
        try:
            return self.RequestHandlerClass.credentials
        except AttributeError:
            return dict()

    def _set_credentials(self, value):
        self.RequestHandlerClass.credentials = value
    credentials = property(_get_credentials, _set_credentials)

    def register_instance(self, instance, *args, **kwargs):
        XMLRPCDispatcher.register_instance(self, instance, *args, **kwargs)
        try:
            name = instance.name
        except AttributeError:
            name = "unknown"
        if hasattr(instance, 'plugins'):
            for pname, pinst in list(instance.plugins.items()):
                for mname in pinst.__rmi__:
                    xmname = "%s.%s" % (pname, mname)
                    fn = getattr(pinst, mname)
                    self.register_function(fn, name=xmname)
        self.logger.info("serving %s at %s" % (name, self.url))

    def serve_forever(self):
        """Serve single requests until (self.serve == False)."""
        self.serve = True
        self.task_thread = threading.Thread(target=self._tasks_thread)
        self.task_thread.start()
        self.logger.info("serve_forever() [start]")
        signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self._handle_shutdown_signal)

        try:
            while self.serve:
                try:
                    self.handle_request()
                except socket.timeout:
                    pass
                except select.error:
                    pass
                except:
                    self.logger.error("Got unexpected error in handle_request",
                                      exc_info=1)
        finally:
            self.logger.info("serve_forever() [stop]")

    def shutdown(self):
        """Signal that automatic service should stop."""
        self.serve = False

    def _handle_shutdown_signal(self, *_):
        self.shutdown()

    def ping(self, *args):
        """Echo response."""
        self.logger.info("ping(%s)" % (", ".join([repr(arg) for arg in args])))
        return args
