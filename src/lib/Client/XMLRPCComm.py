'''XMLRPC/SSL Communication Library (following the ssslib API)'''
__revision__ = '$Revision:$'

from lxml.etree import XML
from ConfigParser import ConfigParser
from xmlrpclib import Fault, ServerProxy
from sys import exc_info
from traceback import extract_tb

class CommunicationError(Exception):
    '''Duplicate the sss.ssslib error API'''
    pass

class comm_lib(object):
    '''This sets up the communication for XMLRPC Bcfg2'''

    def __init__(self):
        self.cf = ConfigParser()
        self.cf.read('/etc/bcfg2.conf')
        location = self.cf.get("components", "bcfg2")
        self.proxy = ServerProxy(location)
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
        for i in range(5):
            try:
                self.response = apply(func, args)
                return
            except Fault, msg:
                raise CommunicationError, msg
            except:
                print "Transient communication error; retrying"
                continue
        (trace, val, trb) = exc_info()
        print "Unexpected communication error after retry"
        for line in extract_tb(trb):
            print '  File "%s", line %i, in %s\n    %s\n' % line
        print "%s: %s\n" % (trace, val)
        del trace, val, trb
        raise CommunicationError, "no connect"

    def RecvMessage(self, handle):
        '''Return cached response'''
        return self.response

    def ClientClose(self, handle):
        '''This is a noop for xmlrpc'''
        pass
