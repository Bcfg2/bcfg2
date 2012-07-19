""" the core of the builtin bcfg2 server """

import os
import sys
import time
import socket
import logging
from Bcfg2.Server.Core import BaseCore
from Bcfg2.Bcfg2Py3k import xmlrpclib, urlparse

logger = logging.getLogger()

class NoExposedMethod (Exception):
    """There is no method exposed with the given name."""


class Core(BaseCore):
    name = 'bcfg2-server'

    def _resolve_exposed_method(self, method_name):
        """Resolve an exposed method.

        Arguments:
        method_name -- name of the method to resolve

        """
        try:
            func = getattr(self, method_name)
        except AttributeError:
            raise NoExposedMethod(method_name)
        if not getattr(func, "exposed", False):
            raise NoExposedMethod(method_name)
        return func

    def _dispatch(self, method, args, dispatch_dict):
        """Custom XML-RPC dispatcher for components.

        method -- XML-RPC method name
        args -- tuple of paramaters to method

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
                result = method_func(*args)
            finally:
                method_done = time.time()
        except xmlrpclib.Fault:
            raise
        except Exception:
            e = sys.exc_info()[1]
            if getattr(e, "log", True):
                self.logger.error(e, exc_info=True)
            raise xmlrpclib.Fault(getattr(e, "fault_code", 1), str(e))
        return result

    def run(self):
        if self.setup['daemon']:
            self._daemonize()

        hostname, port = urlparse(self.setup['location'])[1].split(':')
        server_address = socket.getaddrinfo(hostname,
                                            port,
                                            socket.AF_UNSPEC,
                                            socket.SOCK_STREAM)[0][4]
        try:
            server = XMLRPCServer(self.setup['listen_all'],
                                  server_address,
                                  keyfile=self.setup['key'],
                                  certfile=self.setup['cert'],
                                  register=False,
                                  timeout=1,
                                  ca=self.setup['ca'],
                                  protocol=self.setup['protocol'])
        except:
            err = sys.exc_info()[1]
            self.logger.error("Server startup failed")
            os._exit(1)
        server.register_instance(self)

        try:
            server.serve_forever()
        finally:
            server.server_close()
        self.shutdown()

    def methodHelp(self, method_name):
        try:
            func = self._resolve_exposed_method(method_name)
        except NoExposedMethod:
            return ""
        return func.__doc__
