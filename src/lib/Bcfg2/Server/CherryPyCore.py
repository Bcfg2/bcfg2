""" The core of the `CherryPy <http://www.cherrypy.org/>`_-powered
server. """

import sys
import time
import Bcfg2.Statistics
from Bcfg2.Compat import urlparse, xmlrpclib, b64decode
from Bcfg2.Server.Core import BaseCore
import cherrypy
from cherrypy.lib import xmlrpcutil
from cherrypy._cptools import ErrorTool
from cherrypy.process.plugins import Daemonizer, DropPrivileges, PIDFile


def on_error(*args, **kwargs):  # pylint: disable=W0613
    """ CherryPy error handler that handles :class:`xmlrpclib.Fault`
    objects and so allows for the possibility of returning proper
    error codes. This obviates the need to use
    :func:`cherrypy.lib.xmlrpc.on_error`, the builtin CherryPy xmlrpc
    tool, which does not handle xmlrpclib.Fault objects and returns
    the same error code for every error."""
    err = sys.exc_info()[1]
    if not isinstance(err, xmlrpclib.Fault):
        err = xmlrpclib.Fault(xmlrpclib.INTERNAL_ERROR, str(err))
    xmlrpcutil._set_response(xmlrpclib.dumps(err))  # pylint: disable=W0212

cherrypy.tools.xmlrpc_error = ErrorTool(on_error)


class Core(BaseCore):
    """ The CherryPy-based server core. """

    #: Base CherryPy config for this class.  We enable the
    #: ``xmlrpc_error`` tool created from :func:`on_error` and the
    #: ``bcfg2_authn`` tool created from :func:`do_authn`.
    _cp_config = {'tools.xmlrpc_error.on': True,
                  'tools.bcfg2_authn.on': True}

    def __init__(self, setup):
        BaseCore.__init__(self, setup)

        cherrypy.tools.bcfg2_authn = cherrypy.Tool('on_start_resource',
                                                   self.do_authn)

        #: List of exposed plugin RMI
        self.rmi = self._get_rmi()
        cherrypy.engine.subscribe('stop', self.shutdown)
    __init__.__doc__ = BaseCore.__init__.__doc__.split('.. -----')[0]

    def do_authn(self):
        """ Perform authentication by calling
        :func:`Bcfg2.Server.Core.BaseCore.authenticate`. This is
        implemented as a CherryPy tool."""
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
        """ Handle all XML-RPC calls.  It was necessary to make enough
        changes to the stock CherryPy
        :class:`cherrypy._cptools.XMLRPCController` to support plugin
        RMI and prepending the client address that we just rewrote it.
        It clearly wasn't written with inheritance in mind."""
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
            Bcfg2.Statistics.stats.add_value(rpcmethod,
                                             time.time() - method_start)

        xmlrpcutil.respond(body, 'utf-8', True)
        return cherrypy.serving.response.body

    def _daemonize(self):
        """ Drop privileges with
        :class:`cherrypy.process.plugins.DropPrivileges`, daemonize
        with :class:`cherrypy.process.plugins.Daemonizer`, and write a
        PID file with :class:`cherrypy.process.plugins.PIDFile`. """
        DropPrivileges(cherrypy.engine,
                       uid=self.setup['daemon_uid'],
                       gid=self.setup['daemon_gid'],
                       umask=int(self.setup['umask'], 8)).subscribe()
        Daemonizer(cherrypy.engine).subscribe()
        PIDFile(cherrypy.engine, self.setup['daemon']).subscribe()
        return True

    def _run(self):
        """ Start the server listening. """
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
        return True

    def _block(self):
        """ Enter the blocking infinite server
        loop. :func:`Bcfg2.Server.Core.BaseCore.shutdown` is called on
        exit by a :meth:`subscription
        <cherrypy.process.wspbus.Bus.subscribe>` on the top-level
        CherryPy engine."""
        cherrypy.engine.block()
