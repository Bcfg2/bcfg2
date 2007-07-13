from SocketServer import *
from SimpleXMLRPCServer import *
from tlslite.api import *
#from Bcfg2.tlslite.api import *

s = open("./serverX509Cert.pem").read()
x509 = X509()
x509.parse(s)
certChain = X509CertChain([x509])
s = open("./serverX509Key.pem").read()
privateKey = parsePEMKey(s, private=True)

sessionCache = SessionCache()

class MyHTTPServer(ThreadingMixIn, TLSSocketServerMixIn, SimpleXMLRPCServer):
    db = VerifierDB("./verifierDB")
    db.open()

    def handshake(self, tlsConnection):
        try:
            tlsConnection.handshakeServer(certChain=certChain,
                                          privateKey=privateKey,
                                          verifierDB=self.db,
                                          sessionCache=sessionCache)
            tlsConnection.ignoreAbruptClose = True
            return True
        except TLSError, error:
            print "Handshake failure:", str(error)
            return False

class TLSXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):
    '''TLSXMLRPCRequestHandler overrides SimpleXMLRPCRequestHandler to close
       connections without causing problems. (just the do_POST() is broken)'''
    def do_POST(self):
        """Handles the HTTP POST request.

        Attempts to interpret all HTTP POST requests as XML-RPC calls,
        which are forwarded to the server's _dispatch method for handling.
        """
        
        # Check that the path is legal
        if not self.is_rpc_path_valid():
            self.report_404()
            return
        
        try:
            # Get arguments by reading body of request.
            # We read this in chunks to avoid straining
            # socket.read(); around the 10 or 15Mb mark, some platforms
            # begin to have problems (bug #792570).
            max_chunk_size = 10*1024*1024
            size_remaining = int(self.headers["content-length"])
            L = []
            while size_remaining:
                chunk_size = min(size_remaining, max_chunk_size)
                L.append(self.rfile.read(chunk_size))
                size_remaining -= len(L[-1])
            data = ''.join(L)
            
            # In previous versions of SimpleXMLRPCServer, _dispatch
            # could be overridden in this class, instead of in
            # SimpleXMLRPCDispatcher. To maintain backwards compatibility,
            # check to see if a subclass implements _dispatch and dispatch
            # using that method if present.
            response = self.server._marshaled_dispatch(
                data, getattr(self, '_dispatch', None)
                )
        except: # This should only happen if the module is buggy
            # internal error, report as HTTP server error
            self.send_response(500)
            self.end_headers()
        else:
            # got a valid XML RPC response
            self.send_response(200)
            self.send_header("Content-type", "text/xml")
            self.send_header("Content-length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            
            # shut down the connection
            self.wfile.flush()
            #THIS IS THE ONLY MODIFICATION FROM SimpleXMLRPCRequestHandler's IMPLEMENTATION:
            #self.connection.shutdown(1)
            self.connection.close()
                

def silly(arg="string"):
    print arg
    return arg[::-1]
    
    
httpd = MyHTTPServer(('localhost', 8505), TLSXMLRPCRequestHandler)
httpd.register_introspection_functions()
httpd.register_function(silly)
httpd.serve_forever()
