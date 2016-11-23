""" The core of the builtin Bcfg2 server. """

import os
import sys
import time
import socket
import daemon
import Bcfg2.Options
import Bcfg2.Server.Statistics
from Bcfg2.Server.Core import NetworkCore, NoExposedMethod
from Bcfg2.Compat import xmlrpclib, urlparse
from Bcfg2.Server.SSLServer import XMLRPCServer

from lockfile import LockFailed, LockTimeout
# pylint: disable=E0611
try:
    from daemon.pidfile import TimeoutPIDLockFile
except ImportError:
    from daemon.pidlockfile import TimeoutPIDLockFile
# pylint: enable=E0611


class BuiltinCore(NetworkCore):
    """ The built-in server core """
    name = 'bcfg2-server'

    def __init__(self):
        NetworkCore.__init__(self)

        #: The :class:`Bcfg2.Server.SSLServer.XMLRPCServer` instance
        #: powering this server core
        self.server = None

        daemon_args = dict(uid=Bcfg2.Options.setup.daemon_uid,
                           gid=Bcfg2.Options.setup.daemon_gid,
                           umask=int(Bcfg2.Options.setup.umask, 8),
                           detach_process=True,
                           files_preserve=self._logfilehandles())
        if Bcfg2.Options.setup.daemon:
            daemon_args['pidfile'] = TimeoutPIDLockFile(
                Bcfg2.Options.setup.daemon, acquire_timeout=5)
        #: The :class:`daemon.DaemonContext` used to drop
        #: privileges, write the PID file (with :class:`PidFile`),
        #: and daemonize this core.
        self.context = daemon.DaemonContext(**daemon_args)
    __init__.__doc__ = NetworkCore.__init__.__doc__.split('.. -----')[0]

    def _logfilehandles(self, logger=None):
        """ Get a list of all filehandles logger, that have to be handled
        with DaemonContext.files_preserve to keep looging working.

        :param logger: The logger to get the file handles of. By default,
                       self.logger is used.
        :type logger: logging.Logger
        """
        if logger is None:
            logger = self.logger

        handles = [handler.stream.fileno()
                   for handler in logger.handlers
                   if hasattr(handler, 'stream')]
        if logger.parent:
            handles += self._logfilehandles(logger.parent)
        return handles

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

        method_start = time.time()
        try:
            return method_func(*args)
        except xmlrpclib.Fault:
            raise
        except Exception:
            err = sys.exc_info()[1]
            if getattr(err, "log", True):
                self.logger.error(err, exc_info=True)
            raise xmlrpclib.Fault(getattr(err, "fault_code", 1), str(err))
        finally:
            Bcfg2.Server.Statistics.stats.add_value(
                method,
                time.time() - method_start)

    def _daemonize(self):
        """ Open :attr:`context` to drop privileges, write the PID
        file, and daemonize the server core. """
        # Attempt to ensure lockfile is able to be created and not stale
        try:
            self.context.pidfile.acquire()
        except LockFailed:
            err = sys.exc_info()[1]
            self.logger.error("Failed to daemonize %s: %s" % (self.name, err))
            return False
        except LockTimeout:
            try:  # attempt to break the lock
                os.kill(self.context.pidfile.read_pid(), 0)
            except (OSError, TypeError):  # No process with locked PID
                self.context.pidfile.break_lock()
            else:
                err = sys.exc_info()[1]
                self.logger.error("Failed to daemonize %s: Failed to acquire"
                                  "lock on %s" % (self.name,
                                                  Bcfg2.Options.setup.daemon))
                return False
        else:
            self.context.pidfile.release()

        self.context.open()
        self.logger.info("%s daemonized" % self.name)
        return True

    def _run(self):
        """ Create :attr:`server` to start the server listening. """
        hostname, port = urlparse(Bcfg2.Options.setup.server)[1].split(':')
        server_address = socket.getaddrinfo(hostname,
                                            port,
                                            socket.AF_UNSPEC,
                                            socket.SOCK_STREAM)[0][4]
        try:
            self.server = XMLRPCServer(Bcfg2.Options.setup.listen_all,
                                       server_address,
                                       keyfile=Bcfg2.Options.setup.key,
                                       certfile=Bcfg2.Options.setup.cert,
                                       register=False,
                                       ca=Bcfg2.Options.setup.ca,
                                       protocol=Bcfg2.Options.setup.protocol)
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
