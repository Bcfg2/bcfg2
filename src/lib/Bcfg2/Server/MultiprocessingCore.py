""" The multiprocessing server core is a reimplementation of the
:mod:`Bcfg2.Server.BuiltinCore` that uses the Python
:mod:`multiprocessing` library to offload work to multiple child
processes.  As such, it requires Python 2.6+.

The parent communicates with the children over
:class:`multiprocessing.Queue` objects via a
:class:`Bcfg2.Server.MultiprocessingCore.RPCQueue` object.

A method being called via the RPCQueue must be exposed by the child by
decorating it with :func:`Bcfg2.Server.Core.exposed`.
"""

import time
import threading
import lxml.etree
import multiprocessing
import Bcfg2.Server.Plugin
from itertools import cycle
from Bcfg2.Cache import Cache
from Bcfg2.Compat import Empty, wraps
from Bcfg2.Server.Core import BaseCore, exposed
from Bcfg2.Server.BuiltinCore import Core as BuiltinCore
from multiprocessing.connection import Listener, Client


class DispatchingCache(Cache, Bcfg2.Server.Plugin.Debuggable):
    """ Implementation of :class:`Bcfg2.Cache.Cache` that propagates
    cache expiration events to child nodes. """

    #: The method to send over the pipe to expire the cache
    method = "expire_metadata_cache"

    def __init__(self, *args, **kwargs):
        self.rpc_q = kwargs.pop("queue")
        Bcfg2.Server.Plugin.Debuggable.__init__(self)
        Cache.__init__(self, *args, **kwargs)

    def expire(self, key=None):
        self.rpc_q.publish(self.method, args=[key])
        Cache.expire(self, key=key)


class RPCQueue(Bcfg2.Server.Plugin.Debuggable):
    """ An implementation of a :class:`multiprocessing.Queue` designed
    for several additional use patterns:

    * Random-access reads, based on a key that identifies the data;
    * Publish-subscribe, where a datum is sent to all hosts.

    The subscribers can deal with this as a normal Queue with no
    special handling.
    """
    poll_wait = 3.0

    def __init__(self):
        Bcfg2.Server.Plugin.Debuggable.__init__(self)
        self._terminate = threading.Event()
        self._queues = dict()
        self._listeners = []

    def add_subscriber(self, name):
        """ Add a subscriber to the queue.  This returns the
        :class:`multiprocessing.Queue` object that the subscriber
        should read from.  """
        self._queues[name] = multiprocessing.Queue()
        return self._queues[name]

    def publish(self, method, args=None, kwargs=None):
        """ Publish an RPC call to the queue for consumption by all
        subscribers. """
        for queue in self._queues.values():
            queue.put((None, (method, args or [], kwargs or dict())))

    def rpc(self, dest, method, args=None, kwargs=None):
        """ Make an RPC call to the named subscriber, expecting a
        response.  This opens a
        :class:`multiprocessing.connection.Listener` and passes the
        Listener address to the child as part of the RPC call, so that
        the child can connect to the Listener to submit its results.
        """
        listener = Listener()
        self.logger.debug("Created new RPC listener at %s" % listener.address)
        self._listeners.append(listener)
        try:
            self._queues[dest].put((listener.address,
                                    (method, args or [], kwargs or dict())))
            conn = listener.accept()
            try:
                while not self._terminate.is_set():
                    if conn.poll(self.poll_wait):
                        return conn.recv()
            finally:
                conn.close()
        finally:
            listener.close()
            self._listeners.remove(listener)

    def close(self):
        """ Close queues and connections. """
        self._terminate.set()
        self.logger.debug("Closing RPC queues")
        for name, queue in self._queues.items():
            self.logger.debug("Closing RPC queue to %s" % name)
            queue.close()

        # close any listeners that are waiting for connections
        self.logger.debug("Closing RPC connections")
        for listener in self._listeners:
            self.logger.debug("Closing RPC connection at %s" %
                              listener.address)
            listener.close()


class DualEvent(object):
    """ DualEvent is a clone of :class:`threading.Event` that
    internally implements both :class:`threading.Event` and
    :class:`multiprocessing.Event`. """

    def __init__(self, threading_event=None, multiprocessing_event=None):
        self._threading_event = threading_event or threading.Event()
        self._multiproc_event = multiprocessing_event or \
            multiprocessing.Event()
        if threading_event or multiprocessing_event:
            # initialize internal flag to false, regardless of the
            # state of either object passed in
            self.clear()

    def is_set(self):
        """ Return true if and only if the internal flag is true. """
        return self._threading_event.is_set()

    isSet = is_set

    def set(self):
        """ Set the internal flag to true. """
        self._threading_event.set()
        self._multiproc_event.set()

    def clear(self):
        """ Reset the internal flag to false. """
        self._threading_event.clear()
        self._multiproc_event.clear()

    def wait(self, timeout=None):
        """ Block until the internal flag is true, or until the
        optional timeout occurs. """
        return self._threading_event.wait(timeout=timeout)


class ChildCore(BaseCore):
    """ A child process for :class:`Bcfg2.MultiprocessingCore.Core`.
    This core builds configurations from a given
    :class:`multiprocessing.Pipe`.  Note that this is a full-fledged
    server core; the only input it gets from the parent process is the
    hostnames of clients to render.  All other state comes from the
    FAM. However, this core only is used to render configs; it doesn't
    handle anything else (authentication, probes, etc.) because those
    are all much faster.  There's no reason that it couldn't handle
    those, though, if the pipe communication "protocol" were made more
    robust. """

    #: How long to wait while polling for new RPC commands.  This
    #: doesn't affect the speed with which a command is processed, but
    #: setting it too high will result in longer shutdown times, since
    #: we only check for the termination event from the main process
    #: every ``poll_wait`` seconds.
    poll_wait = 3.0

    def __init__(self, name, setup, rpc_q, terminate):
        """
        :param name: The name of this child
        :type name: string
        :param setup: A Bcfg2 options dict
        :type setup: Bcfg2.Options.OptionParser
        :param read_q: The queue the child will read from for RPC
                       communications from the parent process.
        :type read_q: multiprocessing.Queue
        :param write_q: The queue the child will write the results of
                        RPC calls to.
        :type write_q: multiprocessing.Queue
        :param terminate: An event that flags ChildCore objects to shut
                          themselves down.
        :type terminate: multiprocessing.Event
        """
        BaseCore.__init__(self, setup)

        #: The name of this child
        self.name = name

        #: The :class:`multiprocessing.Event` that will be monitored
        #: to determine when this child should shut down.
        self.terminate = terminate

        #: The queue used for RPC communication
        self.rpc_q = rpc_q

        # override this setting so that the child doesn't try to write
        # the pidfile
        self.setup['daemon'] = False

        # ensure that the child doesn't start a perflog thread
        self.perflog_thread = None

        self._rmi = dict()

    def _run(self):
        return True

    def _daemonize(self):
        return True

    def _dispatch(self, address, data):
        """ Method dispatcher used for commands received from
        the RPC queue. """
        if address is not None:
            # if the key is None, then no response is expected.  we
            # make the return connection before dispatching the actual
            # RPC call so that the parent is blocking for a connection
            # as briefly as possible
            self.logger.debug("Connecting to parent via %s" % address)
            client = Client(address)
        method, args, kwargs = data
        func = None
        rv = None
        if "." in method:
            if method in self._rmi:
                func = self._rmi[method]
            else:
                self.logger.error("%s: Method %s does not exist" % (self.name,
                                                                    method))
        elif not hasattr(self, method):
            self.logger.error("%s: Method %s does not exist" % (self.name,
                                                                method))
        else:  # method is not a plugin RMI, and exists
            func = getattr(self, method)
            if not func.exposed:
                self.logger.error("%s: Method %s is not exposed" % (self.name,
                                                                    method))
                func = None
        if func is not None:
            self.logger.debug("%s: Calling RPC method %s" % (self.name,
                                                             method))
            rv = func(*args, **kwargs)
        if address is not None:
            # if the key is None, then no response is expected
            self.logger.debug("Returning data to parent via %s" % address)
            client.send(rv)

    def _block(self):
        self._rmi = self._get_rmi()
        while not self.terminate.is_set():
            try:
                address, data = self.rpc_q.get(timeout=self.poll_wait)
                threadname = "-".join(str(i) for i in data)
                rpc_thread = threading.Thread(name=threadname,
                                              target=self._dispatch,
                                              args=[address, data])
                rpc_thread.start()
            except Empty:
                pass
            except KeyboardInterrupt:
                break
        self.shutdown()

    def shutdown(self):
        BaseCore.shutdown(self)
        self.logger.info("%s: Closing RPC command queue" % self.name)
        self.rpc_q.close()

        while len(threading.enumerate()) > 1:
            threads = [t for t in threading.enumerate()
                       if t != threading.current_thread()]
            self.logger.info("%s: Waiting for %d thread(s): %s" %
                             (self.name, len(threads),
                              [t.name for t in threads]))
            time.sleep(1)
        self.logger.info("%s: All threads stopped" % self.name)

    def _get_rmi(self):
        rmi = dict()
        for pname, pinst in self._get_rmi_objects().items():
            for crmi in pinst.__child_rmi__:
                if isinstance(crmi, tuple):
                    mname = crmi[1]
                else:
                    mname = crmi
                rmi["%s.%s" % (pname, mname)] = getattr(pinst, mname)
        return rmi

    @exposed
    def expire_metadata_cache(self, client=None):
        """ Expire the metadata cache for a client """
        self.metadata_cache.expire(client)

    @exposed
    def RecvProbeData(self, address, _):
        """ Expire the probe cache for a client """
        self.expire_caches_by_type(Bcfg2.Server.Plugin.Probing,
                                   key=self.resolve_client(address,
                                                           metadata=False)[0])

    @exposed
    def GetConfig(self, client):
        """ Render the configuration for a client """
        self.metadata.update_client_list()
        self.logger.debug("%s: Building configuration for %s" %
                          (self.name, client))
        return lxml.etree.tostring(self.BuildConfiguration(client))


class Core(BuiltinCore):
    """ A multiprocessing core that delegates building the actual
    client configurations to
    :class:`Bcfg2.Server.MultiprocessingCore.ChildCore` objects.  The
    parent process doesn't build any children itself; all calls to
    :func:`GetConfig` are delegated to children. All other calls are
    handled by the parent process. """

    #: How long to wait for a child process to shut down cleanly
    #: before it is terminated.
    shutdown_timeout = 10.0

    def __init__(self, setup):
        BuiltinCore.__init__(self, setup)
        if setup['children'] is None:
            setup['children'] = multiprocessing.cpu_count()

        #: The flag that indicates when to stop child threads and
        #: processes
        self.terminate = DualEvent(threading_event=self.terminate)

        #: A :class:`Bcfg2.Server.MultiprocessingCore.RPCQueue` object
        #: used to send or publish commands to children.
        self.rpc_q = RPCQueue()

        self.metadata_cache = DispatchingCache(queue=self.rpc_q)

        #: A list of children that will be cycled through
        self._all_children = []

        #: An iterator that each child will be taken from in sequence,
        #: to provide a round-robin distribution of render requests
        self.children = None

    def _run(self):
        for cnum in range(self.setup['children']):
            name = "Child-%s" % cnum

            self.logger.debug("Starting child %s" % name)
            child_q = self.rpc_q.add_subscriber(name)
            childcore = ChildCore(name, self.setup, child_q, self.terminate)
            child = multiprocessing.Process(target=childcore.run, name=name)
            child.start()
            self.logger.debug("Child %s started with PID %s" % (name,
                                                                child.pid))
            self._all_children.append(name)
        self.logger.debug("Started %s children: %s" % (len(self._all_children),
                                                       self._all_children))
        self.children = cycle(self._all_children)
        return BuiltinCore._run(self)

    def shutdown(self):
        BuiltinCore.shutdown(self)
        self.logger.info("Closing RPC command queues")
        self.rpc_q.close()

        def term_children():
            """ Terminate all remaining multiprocessing children. """
            for child in multiprocessing.active_children():
                self.logger.error("Waited %s seconds to shut down %s, "
                                  "terminating" % (self.shutdown_timeout,
                                                   child.name))
                child.terminate()

        timer = threading.Timer(self.shutdown_timeout, term_children)
        timer.start()
        while len(multiprocessing.active_children()):
            self.logger.info("Waiting for %s child(ren): %s" %
                             (len(multiprocessing.active_children()),
                              [c.name
                               for c in multiprocessing.active_children()]))
            time.sleep(1)
        timer.cancel()
        self.logger.info("All children shut down")

        while len(threading.enumerate()) > 1:
            threads = [t for t in threading.enumerate()
                       if t != threading.current_thread()]
            self.logger.info("Waiting for %s thread(s): %s" %
                             (len(threads), [t.name for t in threads]))
            time.sleep(1)
        self.logger.info("Shutdown complete")

    def _get_rmi(self):
        child_rmi = dict()
        for pname, pinst in self._get_rmi_objects().items():
            for crmi in pinst.__child_rmi__:
                if isinstance(crmi, tuple):
                    parentname, childname = crmi
                else:
                    parentname = childname = crmi
                child_rmi["%s.%s" % (pname, parentname)] = \
                    "%s.%s" % (pname, childname)

        rmi = BuiltinCore._get_rmi(self)
        for method in rmi.keys():
            if method in child_rmi:
                rmi[method] = self._child_rmi_wrapper(method,
                                                      rmi[method],
                                                      child_rmi[method])
        return rmi

    def _child_rmi_wrapper(self, method, parent_rmi, child_rmi):
        """ Returns a callable that dispatches a call to the given
        child RMI to child processes, and calls the parent RMI locally
        (i.e., in the parent process). """
        @wraps(parent_rmi)
        def inner(*args, **kwargs):
            """ Function that dispatches an RMI call to child
            processes and to the (original) parent function. """
            self.logger.debug("Dispatching RMI call to %s to children: %s" %
                              (method, child_rmi))
            self.rpc_q.publish(child_rmi, args=args, kwargs=kwargs)
            return parent_rmi(*args, **kwargs)

        return inner

    @exposed
    def set_debug(self, address, debug):
        self.rpc_q.set_debug(debug)
        self.rpc_q.publish("set_debug", args=[address, debug])
        self.metadata_cache.set_debug(debug)
        return BuiltinCore.set_debug(self, address, debug)

    @exposed
    def RecvProbeData(self, address, probedata):
        rv = BuiltinCore.RecvProbeData(self, address, probedata)
        # we don't want the children to actually process probe data,
        # so we don't send the data, just the fact that we got some.
        self.rpc_q.publish("RecvProbeData", args=[address, None])
        return rv

    @exposed
    def GetConfig(self, address):
        client = self.resolve_client(address)[0]
        childname = self.children.next()
        self.logger.debug("Building configuration for %s on %s" % (client,
                                                                   childname))
        return self.rpc_q.rpc(childname, "GetConfig", args=[client])

    @exposed
    def get_statistics(self, address):
        stats = dict()

        def _aggregate_statistics(newstats, prefix=None):
            """ Aggregate a set of statistics from a child or parent
            server core.  This adds the statistics to the overall
            statistics dict (optionally prepending a prefix, such as
            "Child-1", to uniquely identify this set of statistics),
            and aggregates it with the set of running totals that are
            kept from all cores. """
            for statname, vals in newstats.items():
                if statname.startswith("ChildCore:"):
                    statname = statname[5:]
                if prefix:
                    prettyname = "%s:%s" % (prefix, statname)
                else:
                    prettyname = statname
                stats[prettyname] = vals
                totalname = "Total:%s" % statname
                if totalname not in stats:
                    stats[totalname] = vals
                else:
                    newmin = min(stats[totalname][0], vals[0])
                    newmax = max(stats[totalname][1], vals[1])
                    newcount = stats[totalname][3] + vals[3]
                    newmean = ((stats[totalname][2] * stats[totalname][3]) +
                               (vals[2] * vals[3])) / newcount
                    stats[totalname] = (newmin, newmax, newmean, newcount)

        stats = dict()
        for childname in self._all_children:
            _aggregate_statistics(
                self.rpc_q.rpc(childname, "get_statistics", args=[address]),
                prefix=childname)
        _aggregate_statistics(BuiltinCore.get_statistics(self, address))
        return stats
