""" bcfg2-test libraries and CLI """

import os
import sys
import shlex
import signal
import fnmatch
import logging
import Bcfg2.Logger
import Bcfg2.Server.Core
from math import ceil
from nose.core import TestProgram
from nose.suite import LazySuite
from unittest import TestCase

try:
    from multiprocessing import Process, Queue, active_children
    HAS_MULTIPROC = True
except ImportError:
    HAS_MULTIPROC = False

    def active_children():
        """active_children() when multiprocessing lib is missing."""
        return []


def get_sigint_handler(core):
    """ Get a function that handles SIGINT/Ctrl-C by shutting down the
    core and exiting properly."""

    def hdlr(sig, frame):  # pylint: disable=W0613
        """ Handle SIGINT/Ctrl-C by shutting down the core and exiting
        properly. """
        core.shutdown()
        os._exit(1)  # pylint: disable=W0212

    return hdlr


class CapturingLogger(object):
    """ Fake logger that captures logging output so that errors are
    only displayed for clients that fail tests """
    def __init__(self, *args, **kwargs):  # pylint: disable=W0613
        self.output = []

    def error(self, msg):
        """ discard error messages """
        self.output.append(msg)

    def warning(self, msg):
        """ discard error messages """
        self.output.append(msg)

    def info(self, msg):
        """ discard error messages """
        self.output.append(msg)

    def debug(self, msg):
        """ discard error messages """
        if Bcfg2.Options.setup.debug:
            self.output.append(msg)

    def reset_output(self):
        """ Reset the captured output """
        self.output = []


class ClientTestFromQueue(TestCase):
    """ A test case that tests a value that has been enqueued by a
    child test process.  ``client`` is the name of the client that has
    been tested; ``result`` is the result from the :class:`ClientTest`
    test.  ``None`` indicates a successful test; a string value
    indicates a failed test; and an exception indicates an error while
    running the test. """
    __test__ = False  # Do not collect

    def __init__(self, client, result):
        TestCase.__init__(self)
        self.client = client
        self.result = result

    def shortDescription(self):
        return "Building configuration for %s" % self.client

    def runTest(self):
        """ parse the result from this test """
        if isinstance(self.result, Exception):
            raise self.result
        assert self.result is None, self.result


class ClientTest(TestCase):
    """ A test case representing the build of all of the configuration for
    a single host.  Checks that none of the build config entities has
    had a failure when it is building.  Optionally ignores some config
    files that we know will cause errors (because they are private
    files we don't have access to, for instance) """
    __test__ = False  # Do not collect
    divider = "-" * 70

    def __init__(self, core, client, ignore=None):
        TestCase.__init__(self)
        self.core = core
        self.core.logger = CapturingLogger()
        self.client = client
        if ignore is None:
            self.ignore = dict()
        else:
            self.ignore = ignore

    def ignore_entry(self, tag, name):
        """ return True if an error on a given entry should be ignored
        """
        if tag in self.ignore:
            if name in self.ignore[tag]:
                return True
            else:
                # try wildcard matching
                for pattern in self.ignore[tag]:
                    if fnmatch.fnmatch(name, pattern):
                        return True
        return False

    def shortDescription(self):
        return "Building configuration for %s" % self.client

    def runTest(self):
        """ run this individual test """
        config = self.core.BuildConfiguration(self.client)
        output = self.core.logger.output[:]
        if output:
            output.append(self.divider)
        self.core.logger.reset_output()

        # check for empty client configuration
        assert len(config.findall("Bundle")) > 0, \
            "\n".join(output + ["%s has no content" % self.client])

        # check for missing bundles
        metadata = self.core.build_metadata(self.client)
        sbundles = [el.get('name') for el in config.findall("Bundle")]
        missing = [b for b in metadata.bundles if b not in sbundles]
        assert len(missing) == 0, \
            "\n".join(output + ["Configuration is missing bundle(s): %s" %
                                ':'.join(missing)])

        # check for unknown packages
        unknown_pkgs = [el.get("name")
                        for el in config.xpath('//Package[@type="unknown"]')
                        if not self.ignore_entry(el.tag, el.get("name"))]
        assert len(unknown_pkgs) == 0, \
            "Configuration contains unknown packages: %s" % \
            ", ".join(unknown_pkgs)

        failures = []
        msg = output + ["Failures:"]
        for failure in config.xpath('//*[@failure]'):
            if not self.ignore_entry(failure.tag, failure.get('name')):
                failures.append(failure)
                msg.append("%s:%s: %s" % (failure.tag, failure.get("name"),
                                          failure.get("failure")))

        assert len(failures) == 0, "\n".join(msg)

    def __str__(self):
        return "ClientTest(%s)" % self.client

    id = __str__


class CLI(object):
    """ The bcfg2-test CLI """
    options = [
        Bcfg2.Options.PositionalArgument(
            "clients", help="Specific clients to build", nargs="*"),
        Bcfg2.Options.Option(
            "--nose-options", cf=("bcfg2_test", "nose_options"),
            type=shlex.split, default=[],
            help='Options to pass to nosetests. Only honored with '
            '--children 0'),
        Bcfg2.Options.Option(
            "--ignore", cf=('bcfg2_test', 'ignore_entries'), default=[],
            dest="test_ignore", type=Bcfg2.Options.Types.comma_list,
            help='Ignore these entries if they fail to build'),
        Bcfg2.Options.Option(
            "--children", cf=('bcfg2_test', 'children'), default=0, type=int,
            help='Spawn this number of children for bcfg2-test (python 2.6+)')]

    def __init__(self):
        parser = Bcfg2.Options.get_parser(
            description="Verify that all clients build without failures",
            components=[Bcfg2.Server.Core.Core, self])
        parser.parse()
        self.logger = logging.getLogger(parser.prog)

        if Bcfg2.Options.setup.children and not HAS_MULTIPROC:
            self.logger.warning("Python multiprocessing library not found, "
                                "running with no children")
            Bcfg2.Options.setup.children = 0

    def get_core(self):
        """ Get a server core, with events handled """
        core = Bcfg2.Server.Core.Core()
        core.load_plugins()
        core.block_for_fam_events(handle_events=True)
        signal.signal(signal.SIGINT, get_sigint_handler(core))
        return core

    def get_ignore(self):
        """ Get a dict of entry tags and names to
        ignore errors from """
        ignore = dict()
        for entry in Bcfg2.Options.setup.test_ignore:
            tag, name = entry.split(":")
            try:
                ignore[tag].append(name)
            except KeyError:
                ignore[tag] = [name]
        return ignore

    def run_child(self, clients, queue):
        """ Run tests for the given clients in a child process, returning
        results via the given Queue """
        core = self.get_core()
        ignore = self.get_ignore()
        for client in clients:
            try:
                ClientTest(core, client, ignore).runTest()
                queue.put((client, None))
            except AssertionError:
                queue.put((client, str(sys.exc_info()[1])))
            except:
                queue.put((client, sys.exc_info()[1]))

        core.shutdown()

    def run(self):
        """ Run bcfg2-test """
        core = self.get_core()
        clients = Bcfg2.Options.setup.clients or core.metadata.clients
        ignore = self.get_ignore()

        if Bcfg2.Options.setup.children:
            if Bcfg2.Options.setup.children > len(clients):
                self.logger.info("Refusing to spawn more children than "
                                 "clients to test, setting children=%s" %
                                 len(clients))
                Bcfg2.Options.setup.children = len(clients)
            perchild = int(ceil(len(clients) /
                                float(Bcfg2.Options.setup.children + 1)))
            queue = Queue()
            for child in range(Bcfg2.Options.setup.children):
                start = child * perchild
                end = (child + 1) * perchild
                child = Process(target=self.run_child,
                                args=(clients[start:end], queue))
                child.start()

            def generate_tests():
                """ Read test results for the clients """
                start = Bcfg2.Options.setup.children * perchild
                for client in clients[start:]:
                    yield ClientTest(core, client, ignore)

                for i in range(start):  # pylint: disable=W0612
                    yield ClientTestFromQueue(*queue.get())
        else:
            def generate_tests():
                """ Run tests for the clients """
                for client in clients:
                    yield ClientTest(core, client, ignore)

        result = TestProgram(
            argv=sys.argv[:1] + Bcfg2.Options.setup.nose_options,
            suite=LazySuite(generate_tests), exit=False)

        # block until all children have completed -- should be
        # immediate since we've already gotten all the results we
        # expect
        for child in active_children():
            child.join()

        core.shutdown()
        if result.success:
            os._exit(0)  # pylint: disable=W0212
        else:
            os._exit(1)  # pylint: disable=W0212
