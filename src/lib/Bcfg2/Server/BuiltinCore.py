""" The core of the builtin Bcfg2 server. """

import sys
import time
import socket
import daemon
import Bcfg2.Statistics
from Bcfg2.Server.Core import BaseCore, NoExposedMethod
from Bcfg2.Compat import xmlrpclib, urlparse
from Bcfg2.SSLServer import XMLRPCServer

from lockfile import LockFailed, LockTimeout
# pylint: disable=E0611
try:
    from daemon.pidfile import TimeoutPIDLockFile
except ImportError:
    from daemon.pidlockfile import TimeoutPIDLockFile
# pylint: enable=E0611


class Core(BaseCore):
    """ The built-in server core """
    name = 'bcfg2-server'

    def __init__(self, setup):
        BaseCore.__init__(self, setup)

        #: The :class:`Bcfg2.SSLServer.XMLRPCServer` instance powering
        #: this server core
        self.server = None

        daemon_args = dict(uid=self.setup['daemon_uid'],
                           gid=self.setup['daemon_gid'],
                           umask=int(self.setup['umask'], 8))
        if self.setup['daemon']:
            daemon_args['pidfile'] = TimeoutPIDLockFile(self.setup['daemon'],
                                                        acquire_timeout=5)
        #: The :class:`daemon.DaemonContext` used to drop
        #: privileges, write the PID file (with :class:`PidFile`),
        #: and daemonize this core.
        self.context = daemon.DaemonContext(**daemon_args)
    __init__.__doc__ = BaseCore.__init__.__doc__.split('.. -----')[0]

    def _dispatch(self, method, args, dispatch_dict):
        """ Dispatch XML-RPC method calls

        :param method: XML-RPC method name
        :type method: string
        :param args: Paramaters to pass to the method
        :type args: tuple
        :param dispatch_dict: A dict of method name -> function that
                              can be used to provide custom mappings
        :type dispatch_dict: dict
        :returns: The return value of the method call
        :raises: :exc:`xmlrpclib.Fault`
        """
        if method in dispatch_dict:
            method_func = dispatch_dict[method]
        else:
            try:
                method_func = self._resolve_exposed_method(method)
            except NoExposedMethod:
                self.logger.error("Unknown method %s" % (method))
                raise xmlrpclib.Fault(xmlrpclib.METHOD_NOT_FOUND,
                                      "Unknown method %s" % method)

        try:
            method_start = time.time()
            try:
                return method_func(*args)
            finally:
                Bcfg2.Statistics.stats.add_value(method,
                                                 time.time() - method_start)
        except xmlrpclib.Fault:
            raise
        except Exception:
            err = sys.exc_info()[1]
            if getattr(err, "log", True):
                self.logger.error(err, exc_info=True)
            raise xmlrpclib.Fault(getattr(err, "fault_code", 1), str(err))

    def _daemonize(self):
        """ Open :attr:`context` to drop privileges, write the PID
        file, and daemonize the server core. """
        try:
            self.context.open()
            self.logger.info("%s daemonized" % self.name)
            return True
        except LockFailed:
            err = sys.exc_info()[1]
            self.logger.error("Failed to daemonize %s: %s" % (self.name, err))
            return False
        except LockTimeout:
            err = sys.exc_info()[1]
            self.logger.error("Failed to daemonize %s: Failed to acquire lock "
                              "on %s" % (self.name, self.setup['daemon']))
            return False

    def _run(self):
        """ Create :attr:`server` to start the server listening. """
        hostname, port = urlparse(self.setup['location'])[1].split(':')
        server_address = socket.getaddrinfo(hostname,
                                            port,
                                            socket.AF_UNSPEC,
                                            socket.SOCK_STREAM)[0][4]
        try:
            self.server = XMLRPCServer(self.setup['listen_all'],
                                       server_address,
                                       keyfile=self.setup['key'],
                                       certfile=self.setup['cert'],
                                       register=False,
                                       timeout=1,
                                       ca=self.setup['ca'],
                                       protocol=self.setup['protocol'])
        except:  # pylint: disable=W0702
            err = sys.exc_info()[1]
            self.logger.error("Server startup failed: %s" % err)
            self.context.close()
            return False
        return True

    def _block(self):
        """ Enter the blocking infinite loop. """
        self.server.register_instance(self)
        try:
            self.server.serve_forever()
        finally:
            self.server.server_close()
            self.context.close()
        self.shutdown()
