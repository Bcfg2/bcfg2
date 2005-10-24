'''XMLRPC/SSL Communication Library (following the ssslib API)'''
__revision__ = '$Revision:$'

from elementtree.ElementTree import XML, tostring
from ConfigParser import ConfigParser
from M2Crypto.m2xmlrpclib import ServerProxy, SSL_Transport
from xmlrpclib import Fault

class CommunicationError(Exception):
    '''Duplicate the sss.ssslib error API'''
    pass

class comm_lib(object):
    '''This sets up the communication for XMLRPC Bcfg2'''

    def __init__(self):
        self.cf = ConfigParser()
        self.cf.read('/etc/bcfg2.conf')
        location = self.cf.get("components", "bcfg2")
        self.proxy = ServerProxy(location, SSL_Transport())
        self.user = 'root'
        self.password = self.cf.get("communication", "password")

    def ClientInit(self, component):
        '''Return a single dummy handle'''
        return "handle"

    def SendMessage(self, handle, msg):
        '''Encode the XML msg as an XML-RPC request'''
        data = XML(msg)
        args = (self.user, self.password)
        if data.tag == 'get-probes':
            funcname = "GetProbes"
        elif data.tag == 'probe-data':
            funcname = "RecvProbeData"
            args = (self.user, self.password, data.getchildren())
        elif data.tag == 'get-config':
            funcname = 'GetConfig'
        elif data.tag == 'upload-statistics':
            funcname = "RecvStats"
            args = (self.user, self.password, msg)
        else:
            print "unsupported function call"
            raise CommunicationError, "foo"
        func = getattr(self.proxy, funcname)
        try:
            self.response = apply(func, args)
        except Fault, msg:
            raise CommunicationError, msg

    def RecvMessage(self, handle):
        '''Return cached response'''
        return self.response

    def ClientClose(self, handle):
        '''This is a noop for xmlrpc'''
        pass
