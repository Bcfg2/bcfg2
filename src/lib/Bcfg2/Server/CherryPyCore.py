""" the core of the CherryPy-powered server """

import sys
import time
import cherrypy
from Bcfg2.Compat import urlparse, xmlrpclib, b64decode
from Bcfg2.Server.Core import BaseCore
from cherrypy.lib import xmlrpcutil
from cherrypy._cptools import ErrorTool
from cherrypy.process.plugins import Daemonizer


def on_error(*args, **kwargs):  # pylint: disable=W0613
    """ define our own error handler that handles xmlrpclib.Fault
    objects and so allows for the possibility of returning proper
    error codes. this obviates the need to use the builtin CherryPy
    xmlrpc tool """
    err = sys.exc_info()[1]
    if not isinstance(err, xmlrpclib.Fault):
        err = xmlrpclib.Fault(xmlrpclib.INTERNAL_ERROR, str(err))
    xmlrpcutil._set_response(xmlrpclib.dumps(err))  # pylint: disable=W0212

cherrypy.tools.xmlrpc_error = ErrorTool(on_error)


class Core(BaseCore):
    """ The CherryPy-based server core """

    _cp_config = {'tools.xmlrpc_error.on': True,
                  'tools.bcfg2_authn.on': True}

    def __init__(self, setup):
        BaseCore.__init__(self, setup)

        cherrypy.tools.bcfg2_authn = cherrypy.Tool('on_start_resource',
                                                   self.do_authn)

        self.rmi = self._get_rmi()
        cherrypy.engine.subscribe('stop', self.shutdown)

    def do_authn(self):
        """ perform authentication """
        try:
            header = cherrypy.request.headers['Authorization']
        except KeyError:
            self.critical_error("No authentication data presented")
        auth_content = header.split()[1]
        auth_content = b64decode(auth_content)
        try:
            username, password = auth_content.split(":")
        except ValueError:
            username = auth_content
            password = ""

        # FIXME: Get client cert
        cert = None
        address = (cherrypy.request.remote.ip, cherrypy.request.remote.name)
        return self.authenticate(cert, username, password, address)

    @cherrypy.expose
    def default(self, *args, **params):  # pylint: disable=W0613
        """ needed to make enough changes to the stock
        XMLRPCController to support plugin.__rmi__ and prepending
        client address that we just rewrote.  it clearly wasn't
        written with inheritance in mind :( """
        rpcparams, rpcmethod = xmlrpcutil.process_body()
        if rpcmethod == 'ERRORMETHOD':
            raise Exception("Unknown error processing XML-RPC request body")
        elif "." not in rpcmethod:
            address = (cherrypy.request.remote.ip,
                       cherrypy.request.remote.name)
            rpcparams = (address, ) + rpcparams

            handler = getattr(self, rpcmethod, None)
            if not handler or not getattr(handler, "exposed", False):
                raise Exception('Method "%s" is not supported' % rpcmethod)
        else:
            try:
                handler = self.rmi[rpcmethod]
            except KeyError:
                raise Exception('Method "%s" is not supported' % rpcmethod)

        method_start = time.time()
        try:
            body = handler(*rpcparams, **params)
        finally:
            self.stats.add_value(rpcmethod, time.time() - method_start)

        xmlrpcutil.respond(body, 'utf-8', True)
        return cherrypy.serving.response.body

    def _daemonize(self):
        Daemonizer(cherrypy.engine).subscribe()

    def _run(self):
        hostname, port = urlparse(self.setup['location'])[1].split(':')
        if self.setup['listen_all']:
            hostname = '0.0.0.0'

        config = {'engine.autoreload.on': False,
                  'server.socket_port': int(port),
                  'server.socket_host': hostname}
        if self.setup['cert'] and self.setup['key']:
            config.update({'server.ssl_module': 'pyopenssl',
                           'server.ssl_certificate': self.setup['cert'],
                           'server.ssl_private_key': self.setup['key']})
        if self.setup['debug']:
            config['log.screen'] = True
        cherrypy.config.update(config)
        cherrypy.tree.mount(self, '/', {'/': self.setup})
        cherrypy.engine.start()

    def _block(self):
        cherrypy.engine.block()
