""" The multiprocessing server core is a reimplementation of the
:mod:`Bcfg2.Server.BuiltinCore` that uses the Python
:mod:`multiprocessing` library to offload work to multiple child
processes.  As such, it requires Python 2.6+.

The parent communicates with the children over
:class:`multiprocessing.Pipe` objects that are wrapped in a
:class:`Bcfg2.Server.MultiprocessingCore.ThreadSafePipeDispatcher` to
make them thread-safe.  Each command passed over the Pipe should be in
the following format::

    (<method>, <args>, <kwargs>)

The parent can also communicate with children over a one-way
:class:`multiprocessing.Queue` object that is used for
publish-subscribe communications, i.e., most XML-RPC commands.
(Setting debug, e.g., doesn't require a response from the children.)

The method must be exposed by the child by decorating it with
:func:`Bcfg2.Server.Core.exposed`.
"""

import time
import threading
import lxml.etree
import multiprocessing
from uuid import uuid4
from itertools import cycle
from Bcfg2.Cache import Cache
from Bcfg2.Compat import Queue, Empty
from Bcfg2.Server.Core import BaseCore, exposed
from Bcfg2.Server.Plugin import Debuggable
from Bcfg2.Server.BuiltinCore import Core as BuiltinCore


class DispatchingCache(Cache, Debuggable):
    """ Implementation of :class:`Bcfg2.Cache.Cache` that propagates
    cache expiration events to child nodes. """

    #: The method to send over the pipe to expire the cache
    method = "expire_cache"

    def __init__(self, *args, **kwargs):
        self.cmd_q = kwargs.pop("queue")
        Debuggable.__init__(self)
        Cache.__init__(self, *args, **kwargs)

    def expire(self, key=None):
        self.cmd_q.put((self.method, [key], dict()))
        Cache.expire(self, key=key)


class PublishSubscribeQueue(object):
    """ An implementation of a :class:`multiprocessing.Queue` designed
    for publish-subscribe use patterns. I.e., a single node adds items
    to the queue, and every other node retrieves the item.  This is
    the 'publish' end; the subscribers can deal with this as a normal
    Queue with no special handling.

    Note that, since this is the publishing end, there's no support
    for getting.
    """

    def __init__(self):
        self._queues = []

    def add_subscriber(self):
        """ Add a subscriber to the queue.  This returns a
        :class:`multiprocessing.Queue` object that is used as the
        subscription end of the queue. """
        new_q = multiprocessing.Queue()
        self._queues.append(new_q)
        return new_q

    def put(self, obj, block=True, timeout=None):
        """ Put ``obj`` into the queue.  See
        :func:`multiprocessing.Queue.put` for more details."""
        for queue in self._queues:
            queue.put(obj, block=block, timeout=timeout)

    def put_nowait(self, obj):
        """ Equivalent to ``put(obj, False)``. """
        self.put(obj, block=False)

    def close(self):
        """ Close the queue.  See :func:`multiprocessing.Queue.close`
        for more details. """
        for queue in self._queues:
            queue.close()


class ThreadSafePipeDispatcher(Debuggable):
    """ This is a wrapper around :class:`multiprocessing.Pipe` objects
    that allows them to be used in multithreaded applications.  When
    performing a ``send()``, a key is included that will be used to
    identify the response.  As responses are received from the Pipe,
    they are added to a dict that is used to get the appropriate
    response for a given thread.

    The remote end of the Pipe must deal with the key being sent with
    the data in a tuple of ``(key, data)``, and it must include the
    key with its response.

    It is the responsibility of the user to ensure that the key is
    unique.

    Note that this adds a bottleneck -- all communication over the
    actual Pipe happens in a single thread.  But for our purposes,
    Pipe communication is fairly minimal and that's an acceptable
    bottleneck."""

    #: How long to wait while polling for new data to send.  This
    #: doesn't affect the speed with which data is sent, but
    #: setting it too high will result in longer shutdown times, since
    #: we only check for the termination event from the main process
    #: every ``poll_wait`` seconds.
    poll_wait = 2.0

    _sentinel = object()

    def __init__(self, terminate):
        Debuggable.__init__(self)

        #: The threading flag that is used to determine when the
        #: threads should stop.
        self.terminate = terminate

        #: The :class:`multiprocessing.Pipe` tuple used by this object
        self.pipe = multiprocessing.Pipe()

        self._mainpipe = self.pipe[0]
        self._recv_dict = dict()
        self._send_queue = Queue()

        self.send_thread = threading.Thread(name="PipeSendThread",
                                            target=self._send_thread)
        self.send_thread.start()
        self.recv_thread = threading.Thread(name="PipeRecvThread",
                                            target=self._recv_thread)
        self.recv_thread.start()

    def _send_thread(self):
        """ Run the single thread through which send requests are passed """
        self.logger.debug("Starting interprocess RPC send thread")
        while not self.terminate.isSet():
            try:
                data = self._send_queue.get(True, self.poll_wait)
                self._mainpipe.send(data)
            except Empty:
                pass
        self.logger.info("Interprocess RPC send thread stopped")

    def send(self, key, data):
        """ Send data with the given unique key """
        self._send_queue.put((key, data))

    def _recv_thread(self):
        """ Run the single thread through which recv requests are passed """
        self.logger.debug("Starting interprocess RPC receive thread")
        while not self.terminate.isSet():
            if self._mainpipe.poll(self.poll_wait):
                key, data = self._mainpipe.recv()
                if key in self._recv_dict:
                    self.logger.error("Duplicate key in received data: %s" %
                                      key)
                    self._mainpipe.close()
                self._recv_dict[key] = data
        self.logger.info("Interprocess RPC receive thread stopped")

    def recv(self, key):
        """ Receive data with the given unique key """
        self.poll(key, timeout=None)
        return self._recv_dict.pop(key)

    def poll(self, key, timeout=_sentinel):
        """ Poll for data with the given unique key.  See
        :func:`multiprocessing.Connection.poll` for the possible
        values of ``timeout``. """
        if timeout is self._sentinel:
            return key in self._recv_dict

        abort = threading.Event()

        if timeout is not None:
            timer = threading.Timer(float(timeout), abort.set)
            timer.start()
        try:
            while not abort.is_set():
                if key in self._recv_dict:
                    return True
            return False
        finally:
            if timeout is not None:
                timer.cancel()

    @staticmethod
    def genkey(base):
        """ Generate a key suitable for use with
        :class:`Bcfg2.Server.MultiprocessingCore.ThreadSafePipeDispatcher`
        send() requests, based on the given data.  The key is
        constructed from the string given, some information about this
        thread, and some random data. """
        thread = threading.current_thread()
        return "%s-%s-%s-%s" % (base, thread.name, thread.ident, uuid4())


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

    def __init__(self, name, setup, rpc_pipe, cmd_q, terminate):
        """
        :param name: The name of this child
        :type name: string
        :param setup: A Bcfg2 options dict
        :type setup: Bcfg2.Options.OptionParser
        :param rpc_pipe: The pipe used for RPC communication with the
                         parent process
        :type rpc_pipe: multiprocessing.Pipe
        :param cmd_q: The queue used for one-way pub-sub
                      communications from the parent process
        :type cmd_q: multiprocessing.Queue
        :param terminate: An event that flags ChildCore objects to shut
                          themselves down.
        :type terminate: multiprocessing.Event
        """
        BaseCore.__init__(self, setup)

        #: The name of this child
        self.name = name

        #: The pipe used for RPC communication with the parent
        self.rpc_pipe = rpc_pipe

        #: The queue used to receive pub-sub commands
        self.cmd_q = cmd_q

        #: The :class:`multiprocessing.Event` that will be monitored
        #: to determine when this child should shut down.
        self.terminate = terminate

        # a list of all rendering threads
        self._threads = []

        # the thread used to process publish-subscribe commands
        self._command_thread = threading.Thread(name="CommandThread",
                                                target=self._dispatch_commands)

        # override this setting so that the child doesn't try to write
        # the pidfile
        self.setup['daemon'] = False

        # ensure that the child doesn't start a perflog thread
        self.perflog_thread = None

    def _run(self):
        self._command_thread.start()
        return True

    def _daemonize(self):
        return True

    def _dispatch_commands(self):
        """ Dispatch commands received via the pub-sub queue interface
        """
        self.logger.debug("Starting %s RPC subscription thread" % self.name)
        while not self.terminate.is_set():
            try:
                data = self.cmd_q.get(True, self.poll_wait)
                self.logger.debug("%s: Processing asynchronous command: %s" %
                                  (self.name, data[0]))
                self._dispatch(data)
            except Empty:
                pass
        self.logger.info("%s RPC subscription thread stopped" % self.name)

    def _dispatch_render(self):
        """ Dispatch render requests received via the RPC pipe
        interface """
        key, data = self.rpc_pipe.recv()
        self.rpc_pipe.send((key, self._dispatch(data)))

    def _reap_threads(self):
        """ Reap rendering threads that have completed """
        for thread in self._threads[:]:
            if not thread.is_alive():
                self._threads.remove(thread)

    def _dispatch(self, data):
        """ Generic method dispatcher used for commands received from
        either the pub-sub queue or the RPC pipe. """
        method, args, kwargs = data
        if not hasattr(self, method):
            self.logger.error("%s: Method %s does not exist" % (self.name,
                                                                method))
            return None

        func = getattr(self, method)
        if func.exposed:
            self.logger.debug("%s: Calling RPC method %s" % (self.name,
                                                             method))
            return func(*args, **kwargs)
        else:
            self.logger.error("%s: Method %s is not exposed" % (self.name,
                                                                method))
            return None

    def _block(self):
        while not self.terminate.isSet():
            try:
                if self.rpc_pipe.poll(self.poll_wait):
                    rpc_thread = threading.Thread(
                        name="Renderer%s" % len(self._threads),
                        target=self._dispatch_render)
                    self._threads.append(rpc_thread)
                    rpc_thread.start()
                self._reap_threads()
            except KeyboardInterrupt:
                break
        self.shutdown()

    def shutdown(self):
        BaseCore.shutdown(self)
        self._reap_threads()
        while len(threading.enumerate()) > 1:
            threads = [t for t in threading.enumerate()
                       if t != threading.current_thread()]
            self.logger.info("%s: Waiting for %d thread(s): %s" %
                             (self.name, len(threads),
                              [t.name for t in threads]))
            time.sleep(1)
            self._reap_threads()
        self.logger.info("%s: All threads stopped" % self.name)

    @exposed
    def set_debug(self, address, debug):
        BaseCore.set_debug(self, address, debug)

    @exposed
    def expire_cache(self, client=None):
        """ Expire the metadata cache for a client """
        self.metadata_cache.expire(client)

    @exposed
    def GetConfig(self, client):
        """ Render the configuration for a client """
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

        #: A dict of child name ->
        #: :class:`Bcfg2.Server.MultiprocessingCore.ThreadSafePipeDispatcher`
        #: objects used to pass render requests to that child.  (The
        #: child is given the other end of the Pipe.)
        self.pipes = dict()

        #: A
        #: :class:`Bcfg2.Server.MultiprocessingCore.PublishSubscribeQueue`
        #: object used to publish commands to all children.
        self.cmd_q = PublishSubscribeQueue()

        #: The flag that indicates when to stop child threads and
        #: processes
        self.terminate = DualEvent(threading_event=self.terminate)

        self.metadata_cache = DispatchingCache(queue=self.cmd_q)

        #: A list of children that will be cycled through
        self._all_children = []

        #: An iterator that each child will be taken from in sequence,
        #: to provide a round-robin distribution of render requests
        self.children = None

    def _run(self):
        for cnum in range(self.setup['children']):
            name = "Child-%s" % cnum

            # create Pipe for render requests
            dispatcher = ThreadSafePipeDispatcher(self.terminate)
            self.pipes[name] = dispatcher

            self.logger.debug("Starting child %s" % name)
            childcore = ChildCore(name, self.setup, dispatcher.pipe[1],
                                  self.cmd_q.add_subscriber(), self.terminate)
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
        self.logger.debug("Closing RPC command queues")
        self.cmd_q.close()

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

    @exposed
    def set_debug(self, address, debug):
        self.cmd_q.put(("set_debug", [address, debug], dict()))
        self.metadata_cache.set_debug(debug)
        for pipe in self.pipes.values():
            pipe.set_debug(debug)
        return BuiltinCore.set_debug(self, address, debug)

    @exposed
    def GetConfig(self, address):
        client = self.resolve_client(address)[0]
        childname = self.children.next()
        self.logger.debug("Building configuration for %s on %s" % (client,
                                                                   childname))
        key = ThreadSafePipeDispatcher.genkey(client)
        pipe = self.pipes[childname]
        pipe.send(key, ("GetConfig", [client], dict()))
        return pipe.recv(key)
