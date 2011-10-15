"""Cobalt component base."""

__revision__ = '$Revision$'

__all__ = ["Component", "exposed", "automatic", "run_component"]

import inspect
import logging
import os
import pydoc
import sys
import time
import threading

import Bcfg2.Logger
from Bcfg2.Statistics import Statistics
from Bcfg2.SSLServer import XMLRPCServer
# Compatibility import
from Bcfg2.Bcfg2Py3k import xmlrpclib, urlparse, fprint

logger = logging.getLogger()

class NoExposedMethod (Exception):
    """There is no method exposed with the given name."""

def run_component(component_cls, listen_all, location, daemon, pidfile_name,
                  to_file, cfile, argv=None, register=True,
                  state_name=False, cls_kwargs={}, extra_getopt='', time_out=10,
                  protocol='xmlrpc/ssl', certfile=None, keyfile=None, ca=None):

    # default settings
    level = logging.INFO

    logging.getLogger().setLevel(level)
    Bcfg2.Logger.setup_logging(component_cls.implementation,
                               to_console=True,
                               to_syslog=True,
                               to_file=to_file,
                               level=level)

    if daemon:
        child_pid = os.fork()
        if child_pid != 0:
            return

        os.setsid()

        child_pid = os.fork()
        if child_pid != 0:
            os._exit(0)

        redirect_file = open("/dev/null", "w+")
        os.dup2(redirect_file.fileno(), sys.__stdin__.fileno())
        os.dup2(redirect_file.fileno(), sys.__stdout__.fileno())
        os.dup2(redirect_file.fileno(), sys.__stderr__.fileno())

        os.chdir(os.sep)

        pidfile = open(pidfile_name or "/dev/null", "w")
        fprint(os.getpid(), pidfile)
        pidfile.close()

    component = component_cls(cfile=cfile, **cls_kwargs)
    up = urlparse(location)
    port = tuple(up[1].split(':'))
    port = (port[0], int(port[1]))
    try:
        server = XMLRPCServer(listen_all,
                              port,
                              keyfile=keyfile,
                              certfile=certfile,
                              register=register,
                              timeout=time_out,
                              ca=ca,
                              protocol=protocol)
    except:
        logger.error("Server startup failed")
        os._exit(1)
    server.register_instance(component)

    try:
        server.serve_forever()
    finally:
        server.server_close()
    component.shutdown()

def exposed(func):
    """Mark a method to be exposed publically.

    Examples:
    class MyComponent (Component):
        @expose
        def my_method (self, param1, param2):
            do_stuff()

    class MyComponent (Component):
        def my_method (self, param1, param2):
            do_stuff()
        my_method = expose(my_method)

    """
    func.exposed = True
    return func

def automatic(func, period=10):
    """Mark a method to be run periodically."""
    func.automatic = True
    func.automatic_period = period
    func.automatic_ts = -1
    return func

def locking(func):
    """Mark a function as being internally thread safe"""
    func.locking = True
    return func

def readonly(func):
    """Mark a function as read-only -- no data effects in component inst"""
    func.readonly = True
    return func

class Component (object):
    """Base component.

    Intended to be served as an instance by Cobalt.Component.XMLRPCServer
    >>> server = Cobalt.Component.XMLRPCServer(location, keyfile)
    >>> component = Cobalt.Component.Component()
    >>> server.serve_instance(component)

    Class attributes:
    name -- logical component name (e.g., "queue-manager", "process-manager")
    implementation -- implementation identifier (e.g., "BlueGene/L", "BlueGene/P")

    Methods:
    save -- pickle the component to a file
    do_tasks -- perform automatic tasks for the component

    """

    name = "component"
    implementation = "generic"

    def __init__(self, **kwargs):
        """Initialize a new component.

        Keyword arguments:
        statefile -- file in which to save state automatically

        """
        self.statefile = kwargs.get("statefile", None)
        self.logger = logging.getLogger("%s %s" % (self.implementation, self.name))
        self.lock = threading.Lock()
        self.instance_statistics = Statistics()

    def do_tasks(self):
        """Perform automatic tasks for the component.

        Automatic tasks are member callables with an attribute
        automatic == True.

        """
        for name, func in inspect.getmembers(self):
            if name == '__call__':
                if getattr(func, "automatic", False):
                    need_to_lock = not getattr(func, 'locking', False)
                    if (time.time() - func.automatic_ts) > \
                       func.automatic_period:
                        if need_to_lock:
                            t1 = time.time()
                            self.lock.acquire()
                            t2 = time.time()
                            self.instance_statistics.add_value('component_lock', t2-t1)
                        try:
                            mt1 = time.time()
                            try:
                                func()
                            except:
                                self.logger.error("Automatic method %s failed" \
                                                  % (name), exc_info=1)
                        finally:
                            mt2 = time.time()

                        if need_to_lock:
                            self.lock.release()
                        self.instance_statistics.add_value(name, mt2-mt1)
                        func.__dict__['automatic_ts'] = time.time()

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
        need_to_lock = True
        if method in dispatch_dict:
            method_func = dispatch_dict[method]
        else:
            try:
                method_func = self._resolve_exposed_method(method)
            except NoExposedMethod:
                self.logger.error("Unknown method %s" % (method))
                raise xmlrpclib.Fault(7, "Unknown method %s" % method)
            except Exception:
                e = sys.exc_info()[1]
                if getattr(e, "log", True):
                    self.logger.error(e, exc_info=True)
                raise xmlrpclib.Fault(getattr(e, "fault_code", 1), str(e))

        if getattr(method_func, 'locking', False):
            need_to_lock = False
        if need_to_lock:
            lock_start = time.time()
            self.lock.acquire()
            lock_done = time.time()
        try:
            method_start = time.time()
            try:
                result = method_func(*args)
            finally:
                method_done = time.time()
                if need_to_lock:
                    self.lock.release()
                    self.instance_statistics.add_value('component_lock',
                                                       lock_done - lock_start)
                self.instance_statistics.add_value(method, method_done - method_start)
        except xmlrpclib.Fault:
            raise
        except Exception:
            e = sys.exc_info()[1]
            if getattr(e, "log", True):
                self.logger.error(e, exc_info=True)
            raise xmlrpclib.Fault(getattr(e, "fault_code", 1), str(e))
        return result

    def listMethods(self):
        """Custom XML-RPC introspective method list."""
        return [
            name for name, func in inspect.getmembers(self, callable)
            if getattr(func, "exposed", False)
        ]
    listMethods = exposed(listMethods)

    def methodHelp(self, method_name):
        """Custom XML-RPC introspective method help.

        Arguments:
        method_name -- name of method to get help on

        """
        try:
            func = self._resolve_exposed_method(method_name)
        except NoExposedMethod:
            return ""
        return pydoc.getdoc(func)
    methodHelp = exposed(methodHelp)

    def get_name(self):
        """The name of the component."""
        return self.name
    get_name = exposed(get_name)

    def get_implementation(self):
        """The implementation of the component."""
        return self.implementation
    get_implementation = exposed(get_implementation)

    def get_statistics(self, _):
        """Get current statistics about component execution"""
        return self.instance_statistics.display()
    get_statistics = exposed(get_statistics)
