""" the core of the CherryPy-powered server """

import sys
import base64
import atexit
import cherrypy
import Bcfg2.Options
from Bcfg2.Bcfg2Py3k import urlparse, xmlrpclib
from Bcfg2.Server.Core import BaseCore
from cherrypy.lib import xmlrpcutil
from cherrypy._cptools import ErrorTool

if cherrypy.engine.state == 0:
    cherrypy.engine.start(blocking=False)
    atexit.register(cherrypy.engine.stop)

# define our own error handler that handles xmlrpclib.Fault objects
# and so allows for the possibility of returning proper error
# codes. this obviates the need to use the builtin CherryPy xmlrpc
# tool
def on_error(*args, **kwargs):
    err = sys.exc_info()[1]
    if not isinstance(err, xmlrpclib.Fault):
        err = xmlrpclib.Fault(xmlrpclib.INTERNAL_ERROR, str(err))
    xmlrpcutil._set_response(xmlrpclib.dumps(err))
cherrypy.tools.xmlrpc_error = ErrorTool(on_error)


class Core(BaseCore):
    _cp_config = {'tools.xmlrpc_error.on': True,
                  'tools.bcfg2_authn.on': True}

    def __init__(self, *args, **kwargs):
        BaseCore.__init__(self, *args, **kwargs)

        cherrypy.tools.bcfg2_authn = cherrypy.Tool('on_start_resource',
                                                   self.do_authn)

        self.rmi = self._get_rmi()

    def do_authn(self):
        try:
            header = cherrypy.request.headers['Authorization']
        except KeyError:
            self.critical_error("No authentication data presented")
        auth_type, auth_content = header.split()
        try:
            # py3k compatibility
            auth_content = base64.standard_b64decode(auth_content)
        except TypeError:
            auth_content = \
                base64.standard_b64decode(bytes(auth_content.encode('ascii')))
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
        
        # FIXME: Get client cert
        cert = None
        address = (cherrypy.request.remote.ip, cherrypy.request.remote.name)
        return self.authenticate(cert, username, password, address)

    @cherrypy.expose
    def default(self, *vpath, **params):
        # needed to make enough changes to the stock XMLRPCController
        # to support plugin.__rmi__ and prepending client address that
        # we just rewrote.  it clearly wasn't written with inheritance
        # in mind :(
        rpcparams, rpcmethod = xmlrpcutil.process_body()
        if "." not in rpcmethod:
            address = (cherrypy.request.remote.ip, cherrypy.request.remote.name)
            rpcparams = (address, ) + rpcparams

            handler = getattr(self, rpcmethod)
            if not handler or not getattr(handler, "exposed", False):
                raise Exception('method "%s" is not supported' % attr)
        else:
            try:
                handler = self.rmi[rpcmethod]
            except:
                raise Exception('method "%s" is not supported' % rpcmethod)

        body = handler(*rpcparams, **params)
        
        xmlrpcutil.respond(body, 'utf-8', True)
        return cherrypy.serving.response.body

    def run(self):
        hostname, port = urlparse(self.setup['location'])[1].split(':')
        if self.setup['listen_all']:
            hostname = '0.0.0.0'

        config = {'engine.autoreload.on': False,
                  'server.socket_port': int(port)}
        if self.setup['cert'] and self.setup['key']:
            config.update({'server.ssl_module': 'pyopenssl',
                           'server.ssl_certificate': self.setup['cert'],
                           'server.ssl_private_key': self.setup['key']})
        if self.setup['debug']:
            config['log.screen'] = True
        cherrypy.config.update(config)
        cherrypy.quickstart(self, config={'/': self.setup})
                                                        

def parse_opts(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    optinfo = dict()
    optinfo.update(Bcfg2.Options.CLI_COMMON_OPTIONS)
    optinfo.update(Bcfg2.Options.SERVER_COMMON_OPTIONS)
    optinfo.update(Bcfg2.Options.DAEMON_COMMON_OPTIONS)
    setup = Bcfg2.Options.OptionParser(optinfo, argv=argv)
    setup.parse(argv)
    return setup

def application(environ, start_response):
    """ running behind Apache as a WSGI app is not currently
    supported, but I'm keeping this code here because I hope for it to
    be supported some day.  we'll need to set up an AMQP task queue
    and related magic for that to happen, though. """
    cherrypy.config.update({'environment': 'embedded'})
    setup = parse_opts(argv=['-C', environ['config']])
    root = Core(setup, start_fam_thread=True)
    cherrypy.tree.mount(root)
    return cherrypy.tree(environ, start_response)
