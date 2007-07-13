from tlslite.api import XMLRPCTransport
from xmlrpclib import ServerProxy
from tlslite.integration.ClientHelper import ClientHelper

#Authenticate server based on its X.509 fingerprint
class DTXMLRPCTransport(XMLRPCTransport, ClientHelper):
    def __init__(self,
                 username=None, password=None, sharedKey=None,
                 certChain=None, privateKey=None,
                 cryptoID=None, protocol=None,
                 x509Fingerprint=None,
                 x509TrustList=None, x509CommonName=None,
                 settings=None,
                 use_datetime=0):
       self._use_datetime = use_datetime #this looks like a bug in tlslite. Perhaps just add this over there.
       ClientHelper.__init__(self,
                username, password, sharedKey,
                certChain, privateKey,
                cryptoID, protocol,
                x509Fingerprint,
                x509TrustList, x509CommonName,
                settings)
	
#sha1 fingerprint: ea38c8b6f73b5df8d77bf1e16652d9b8757a7310
serverFingerprint = "ea38c8b6f73b5df8d77bf1e16652d9b8757a7310"

transport = DTXMLRPCTransport(username="name", password="secret",x509Fingerprint=serverFingerprint.lower())
server = ServerProxy("https://localhost:8505", transport)

#print server.system.listMethods()

print(server.silly("Kerbapp 1!"))