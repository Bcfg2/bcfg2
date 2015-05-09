"""This contains all Bcfg2 Client modules"""

import os
import sys
import stat
import time
import fcntl
import socket
import fnmatch
import logging
import argparse
import tempfile
import Bcfg2.Logger
import Bcfg2.Options
from Bcfg2.Client import XML
from Bcfg2.Client import Proxy
from Bcfg2.Client import Tools
from Bcfg2.Utils import locked, Executor, safe_input
from Bcfg2.version import __version__
# pylint: disable=W0622
from Bcfg2.Compat import xmlrpclib, walk_packages, any, all, cmp
# pylint: enable=W0622


def cmpent(ent1, ent2):
    """Sort entries."""
    if ent1.tag != ent2.tag:
        return cmp(ent1.tag, ent2.tag)
    else:
        return cmp(ent1.get('name'), ent2.get('name'))


def matches_entry(entryspec, entry):
    """ Determine if the Decisions-style entry specification matches
    the entry.  Both are tuples of (tag, name).  The entryspec can
    handle the wildcard * in either position. """
    if entryspec == entry:
        return True
    return all(fnmatch.fnmatch(entry[i], entryspec[i]) for i in [0, 1])


def matches_white_list(entry, whitelist):
    """ Return True if (<entry tag>, <entry name>) is in the given
    whitelist. """
    return any(matches_entry(we, (entry.tag, entry.get('name')))
               for we in whitelist)


def passes_black_list(entry, blacklist):
    """ Return True if (<entry tag>, <entry name>) is not in the given
    blacklist. """
    return not any(matches_entry(be, (entry.tag, entry.get('name')))
                   for be in blacklist)


def prompt(msg):
    """ Helper to give a yes/no prompt to the user.  Flushes input
    buffers, handles exceptions, etc.  Returns True if the user
    answers in the affirmative, False otherwise.

    :param msg: The message to show to the user.  The message is not
                altered in any way for display; i.e., it should
                contain "[y/N]" if desired, etc.
    :type msg: string
    :returns: bool - True if yes, False if no """
    try:
        ans = safe_input(msg)
        return ans in ['y', 'Y']
    except UnicodeEncodeError:
        ans = input(msg.encode('utf-8'))
        return ans in ['y', 'Y']
    except (EOFError, KeyboardInterrupt):
        # handle ^C
        raise SystemExit(1)
    except:
        print("Error while reading input: %s" % sys.exc_info()[1])
        return False


class ClientDriverAction(Bcfg2.Options.ComponentAction):
    """ Action to load client drivers """
    bases = ['Bcfg2.Client.Tools']
    fail_silently = True


class Client(object):
    """ The main Bcfg2 client class """

    options = Proxy.ComponentProxy.options + [
        Bcfg2.Options.Common.syslog,
        Bcfg2.Options.Common.interactive,
        Bcfg2.Options.BooleanOption(
            "-q", "--quick", help="Disable some checksum verification"),
        Bcfg2.Options.Option(
            cf=('client', 'probe_timeout'),
            type=Bcfg2.Options.Types.timeout,
            help="Timeout when running client probes"),
        Bcfg2.Options.Option(
            "-b", "--only-bundles", default=[],
            type=Bcfg2.Options.Types.colon_list,
            help='Only configure the given bundle(s)'),
        Bcfg2.Options.Option(
            "-B", "--except-bundles", default=[],
            type=Bcfg2.Options.Types.colon_list,
            help='Configure everything except the given bundle(s)'),
        Bcfg2.Options.ExclusiveOptionGroup(
            Bcfg2.Options.BooleanOption(
                "-Q", "--bundle-quick",
                help='Only verify the given bundle(s)'),
            Bcfg2.Options.Option(
                '-r', '--remove',
                choices=['all', 'services', 'packages', 'users'],
                help='Force removal of additional configuration items')),
        Bcfg2.Options.ExclusiveOptionGroup(
            Bcfg2.Options.PathOption(
                '-f', '--file', type=argparse.FileType('rb'),
                help='Configure from a file rather than querying the server'),
            Bcfg2.Options.PathOption(
                '-c', '--cache', type=argparse.FileType('wb'),
                help='Store the configuration in a file')),
        Bcfg2.Options.BooleanOption(
            '--exit-on-probe-failure', default=True,
            cf=('client', 'exit_on_probe_failure'),
            help="The client should exit if a probe fails"),
        Bcfg2.Options.Option(
            '-p', '--profile', cf=('client', 'profile'),
            help='Assert the given profile for the host'),
        Bcfg2.Options.Option(
            '-l', '--decision', cf=('client', 'decision'),
            choices=['whitelist', 'blacklist', 'none'],
            help='Run client in server decision list mode'),
        Bcfg2.Options.BooleanOption(
            "-O", "--no-lock", help='Omit lock check'),
        Bcfg2.Options.PathOption(
            cf=('components', 'lockfile'), default='/var/lock/bcfg2.run',
            help='Client lock file'),
        Bcfg2.Options.BooleanOption(
            "-n", "--dry-run", help='Do not actually change the system'),
        Bcfg2.Options.Option(
            "-D", "--drivers", cf=('client', 'drivers'),
            type=Bcfg2.Options.Types.comma_list,
            default=[m[1] for m in walk_packages(path=Tools.__path__)],
            action=ClientDriverAction, help='Client drivers'),
        Bcfg2.Options.BooleanOption(
            "-e", "--show-extra", help='Enable extra entry output'),
        Bcfg2.Options.BooleanOption(
            "-k", "--kevlar", help='Run in bulletproof mode'),
        Bcfg2.Options.BooleanOption(
            "-i", "--only-important",
            help='Only configure the important entries')]

    def __init__(self):
        self.config = None
        self._proxy = None
        self.logger = logging.getLogger('bcfg2')
        self.cmd = Executor(Bcfg2.Options.setup.probe_timeout)
        self.tools = []
        self.times = dict()
        self.times['initialization'] = time.time()

        if Bcfg2.Options.setup.bundle_quick:
            if (not Bcfg2.Options.setup.only_bundles and
                    not Bcfg2.Options.setup.except_bundles):
                self.logger.error("-Q option requires -b or -B")
                raise SystemExit(1)
        if Bcfg2.Options.setup.remove == 'services':
            self.logger.error("Service removal is nonsensical; "
                              "removed services will only be disabled")
        if not Bcfg2.Options.setup.server.startswith('https://'):
            Bcfg2.Options.setup.server = \
                'https://' + Bcfg2.Options.setup.server

        #: A dict of the state of each entry.  Keys are the entries.
        #: Values are boolean: True means that the entry is good,
        #: False means that the entry is bad.
        self.states = {}
        self.whitelist = []
        self.blacklist = []
        self.removal = []
        self.unhandled = []
        self.logger = logging.getLogger(__name__)

    def _probe_failure(self, probename, msg):
        """ handle failure of a probe in the way the user wants us to
        (exit or continue) """
        message = "Failed to execute probe %s: %s" % (probename, msg)
        if Bcfg2.Options.setup.exit_on_probe_failure:
            self.fatal_error(message)
        else:
            self.logger.error(message)

    def run_probe(self, probe):
        """Execute probe."""
        name = probe.get('name')
        self.logger.info("Running probe %s" % name)
        ret = XML.Element("probe-data", name=name, source=probe.get('source'))
        try:
            scripthandle, scriptname = tempfile.mkstemp()
            if sys.hexversion >= 0x03000000:
                script = os.fdopen(scripthandle, 'w',
                                   encoding=Bcfg2.Options.setup.encoding)
            else:
                script = os.fdopen(scripthandle, 'w')
            try:
                script.write("#!%s\n" %
                             (probe.attrib.get('interpreter', '/bin/sh')))
                if sys.hexversion >= 0x03000000:
                    script.write(probe.text)
                else:
                    script.write(probe.text.encode('utf-8'))
                script.close()
                os.chmod(scriptname,
                         stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH |
                         stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH |
                         stat.S_IWUSR)  # 0755
                rv = self.cmd.run(scriptname)
                if rv.stderr:
                    self.logger.warning("Probe %s has error output: %s" %
                                        (name, rv.stderr))
                if not rv.success:
                    self._probe_failure(name, "Return value %s" % rv.retval)
                self.logger.info("Probe %s has result:" % name)
                self.logger.info(rv.stdout)
                if sys.hexversion >= 0x03000000:
                    ret.text = rv.stdout
                else:
                    ret.text = rv.stdout.decode('utf-8')
            finally:
                os.unlink(scriptname)
        except SystemExit:
            raise
        except:
            self._probe_failure(name, sys.exc_info()[1])
        return ret

    def fatal_error(self, message):
        """Signal a fatal error."""
        self.logger.error("Fatal error: %s" % (message))
        raise SystemExit(1)

    @property
    def proxy(self):
        """ get an XML-RPC proxy to the server """
        if self._proxy is None:
            self._proxy = Proxy.ComponentProxy()
        return self._proxy

    def run_probes(self):
        """ run probes and upload probe data """
        try:
            probes = XML.XML(str(self.proxy.GetProbes()))
        except (Proxy.ProxyError,
                Proxy.CertificateError,
                socket.gaierror,
                socket.error):
            err = sys.exc_info()[1]
            self.fatal_error("Failed to download probes from bcfg2: %s" % err)
        except XML.ParseError:
            err = sys.exc_info()[1]
            self.fatal_error("Server returned invalid probe requests: %s" %
                             err)

        self.times['probe_download'] = time.time()

        # execute probes
        probedata = XML.Element("ProbeData")
        for probe in probes.findall(".//probe"):
            probedata.append(self.run_probe(probe))

        if len(probes.findall(".//probe")) > 0:
            try:
                # upload probe responses
                self.proxy.RecvProbeData(
                    XML.tostring(probedata,
                                 xml_declaration=False).decode('utf-8'))
            except Proxy.ProxyError:
                err = sys.exc_info()[1]
                self.fatal_error("Failed to upload probe data: %s" % err)

        self.times['probe_upload'] = time.time()

    def get_config(self):
        """ load the configuration, either from the cached
        configuration file (-f), or from the server """
        if Bcfg2.Options.setup.file:
            # read config from file
            try:
                self.logger.debug("Reading cached configuration from %s" %
                                  Bcfg2.Options.setup.file.name)
                return Bcfg2.Options.setup.file.read()
            except IOError:
                self.fatal_error("Failed to read cached configuration from: %s"
                                 % Bcfg2.Options.setup.file.name)
        else:
            # retrieve config from server
            if Bcfg2.Options.setup.profile:
                try:
                    self.proxy.AssertProfile(Bcfg2.Options.setup.profile)
                except Proxy.ProxyError:
                    err = sys.exc_info()[1]
                    self.fatal_error("Failed to set client profile: %s" % err)

            try:
                self.proxy.DeclareVersion(__version__)
            except (xmlrpclib.Fault,
                    Proxy.ProxyError,
                    Proxy.CertificateError,
                    socket.gaierror,
                    socket.error):
                err = sys.exc_info()[1]
                self.fatal_error("Failed to declare version: %s" % err)

            self.run_probes()

            if Bcfg2.Options.setup.decision in ['whitelist', 'blacklist']:
                try:
                    # TODO: read decision list from --decision-list
                    Bcfg2.Options.setup.decision_list = \
                        self.proxy.GetDecisionList(
                            Bcfg2.Options.setup.decision)
                    self.logger.info("Got decision list from server:")
                    self.logger.info(Bcfg2.Options.setup.decision_list)
                except Proxy.ProxyError:
                    err = sys.exc_info()[1]
                    self.fatal_error("Failed to get decision list: %s" % err)

            try:
                rawconfig = self.proxy.GetConfig().encode('utf-8')
            except Proxy.ProxyError:
                err = sys.exc_info()[1]
                self.fatal_error("Failed to download configuration from "
                                 "Bcfg2: %s" % err)

            self.times['config_download'] = time.time()

        if Bcfg2.Options.setup.cache:
            try:
                Bcfg2.Options.setup.cache.write(rawconfig)
                os.chmod(Bcfg2.Options.setup.cache.name, 384)  # 0600
            except IOError:
                self.logger.warning("Failed to write config cache file %s" %
                                    (Bcfg2.Options.setup.cache))
            self.times['caching'] = time.time()

        return rawconfig

    def parse_config(self, rawconfig):
        """ Parse the XML configuration received from the Bcfg2 server """
        try:
            self.config = XML.XML(rawconfig)
        except XML.ParseError:
            syntax_error = sys.exc_info()[1]
            self.fatal_error("The configuration could not be parsed: %s" %
                             syntax_error)

        self.load_tools()

        # find entries not handled by any tools
        self.unhandled = [entry for struct in self.config
                          for entry in struct
                          if entry not in self.handled]

        if self.unhandled:
            self.logger.error("The following entries are not handled by any "
                              "tool:")
            for entry in self.unhandled:
                self.logger.error("%s:%s:%s" % (entry.tag, entry.get('type'),
                                                entry.get('name')))

        # find duplicates
        self.find_dups(self.config)

        pkgs = [(entry.get('name'), entry.get('origin'))
                for struct in self.config
                for entry in struct
                if entry.tag == 'Package']
        if pkgs:
            self.logger.debug("The following packages are specified in bcfg2:")
            self.logger.debug([pkg[0] for pkg in pkgs if pkg[1] is None])
            self.logger.debug("The following packages are prereqs added by "
                              "Packages:")
            self.logger.debug([pkg[0] for pkg in pkgs if pkg[1] == 'Packages'])

        self.times['config_parse'] = time.time()

    def run(self):
        """Perform client execution phase."""
        # begin configuration
        self.times['start'] = time.time()

        self.logger.info("Starting Bcfg2 client run at %s" %
                         self.times['start'])

        self.parse_config(self.get_config().decode('utf-8'))

        if self.config.tag == 'error':
            self.fatal_error("Server error: %s" % (self.config.text))

        if Bcfg2.Options.setup.bundle_quick:
            newconfig = XML.XML('<Configuration/>')
            for bundle in self.config.getchildren():
                name = bundle.get("name")
                if (name and (name in Bcfg2.Options.setup.only_bundles or
                              name not in Bcfg2.Options.setup.except_bundles)):
                    newconfig.append(bundle)
            self.config = newconfig

        if not Bcfg2.Options.setup.no_lock:
            # check lock here
            try:
                lockfile = open(Bcfg2.Options.setup.lockfile, 'w')
                if locked(lockfile.fileno()):
                    self.fatal_error("Another instance of Bcfg2 is running. "
                                     "If you want to bypass the check, run "
                                     "with the -O/--no-lock option")
            except SystemExit:
                raise
            except:
                lockfile = None
                self.logger.error("Failed to open lockfile %s: %s" %
                                  (Bcfg2.Options.setup.lockfile,
                                   sys.exc_info()[1]))

        # execute the configuration
        self.Execute()

        if not Bcfg2.Options.setup.no_lock:
            # unlock here
            if lockfile:
                try:
                    fcntl.lockf(lockfile.fileno(), fcntl.LOCK_UN)
                    os.remove(Bcfg2.Options.setup.lockfile)
                except OSError:
                    self.logger.error("Failed to unlock lockfile %s" %
                                      lockfile.name)

        if (not Bcfg2.Options.setup.file and
                not Bcfg2.Options.setup.bundle_quick):
            # upload statistics
            feedback = self.GenerateStats()

            try:
                self.proxy.RecvStats(
                    XML.tostring(feedback,
                                 xml_declaration=False).decode('utf-8'))
            except Proxy.ProxyError:
                err = sys.exc_info()[1]
                self.logger.error("Failed to upload configuration statistics: "
                                  "%s" % err)
                raise SystemExit(2)

        self.logger.info("Finished Bcfg2 client run at %s" % time.time())

    def load_tools(self):
        """ Load all applicable client tools """
        for tool in Bcfg2.Options.setup.drivers:
            try:
                self.tools.append(tool(self.config))
            except Tools.ToolInstantiationError:
                continue
            except:
                self.logger.error("Failed to instantiate tool %s" % tool,
                                  exc_info=1)

        for tool in self.tools[:]:
            for conflict in getattr(tool, 'conflicts', []):
                for item in self.tools:
                    if item.name == conflict:
                        self.tools.remove(item)

        self.logger.info("Loaded tool drivers:")
        self.logger.info([tool.name for tool in self.tools])

        deprecated = [tool.name for tool in self.tools if tool.deprecated]
        if deprecated:
            self.logger.warning("Loaded deprecated tool drivers:")
            self.logger.warning(deprecated)
        experimental = [tool.name for tool in self.tools if tool.experimental]
        if experimental:
            self.logger.warning("Loaded experimental tool drivers:")
            self.logger.warning(experimental)

    def find_dups(self, config):
        """ Find duplicate entries and warn about them """
        entries = dict()
        for struct in config:
            for entry in struct:
                for tool in self.tools:
                    if tool.handlesEntry(entry):
                        pkey = tool.primarykey(entry)
                        if pkey in entries:
                            entries[pkey] += 1
                        else:
                            entries[pkey] = 1
        multi = [e for e, c in entries.items() if c > 1]
        if multi:
            self.logger.debug("The following entries are included multiple "
                              "times:")
            for entry in multi:
                self.logger.debug(entry)

    def promptFilter(self, msg, entries):
        """Filter a supplied list based on user input."""
        ret = []
        entries.sort(key=lambda e: e.tag + ":" + e.get('name'))
        for entry in entries[:]:
            if entry in self.unhandled:
                # don't prompt for entries that can't be installed
                continue
            if 'qtext' in entry.attrib:
                iprompt = entry.get('qtext')
            else:
                iprompt = msg % (entry.tag, entry.get('name'))
            if prompt(iprompt):
                ret.append(entry)
        return ret

    def __getattr__(self, name):
        if name in ['extra', 'handled', 'modified', '__important__']:
            ret = []
            for tool in self.tools:
                ret += getattr(tool, name)
            return ret
        elif name in self.__dict__:
            return self.__dict__[name]
        raise AttributeError(name)

    def InstallImportant(self):
        """Install important entries

        We also process the decision mode stuff here because we want to prevent
        non-whitelisted/blacklisted 'important' entries from being installed
        prior to determining the decision mode on the client.
        """
        # Need to process decision stuff early so that dryrun mode
        # works with it
        self.whitelist = [entry for entry in self.states
                          if not self.states[entry]]
        if not Bcfg2.Options.setup.file:
            if Bcfg2.Options.setup.decision == 'whitelist':
                dwl = Bcfg2.Options.setup.decision_list
                w_to_rem = [e for e in self.whitelist
                            if not matches_white_list(e, dwl)]
                if w_to_rem:
                    self.logger.info("In whitelist mode: "
                                     "suppressing installation of:")
                    self.logger.info(["%s:%s" % (e.tag, e.get('name'))
                                      for e in w_to_rem])
                    self.whitelist = [x for x in self.whitelist
                                      if x not in w_to_rem]
            elif Bcfg2.Options.setup.decision == 'blacklist':
                b_to_rem = \
                    [e for e in self.whitelist
                     if not
                     passes_black_list(e, Bcfg2.Options.setup.decision_list)]
                if b_to_rem:
                    self.logger.info("In blacklist mode: "
                                     "suppressing installation of:")
                    self.logger.info(["%s:%s" % (e.tag, e.get('name'))
                                      for e in b_to_rem])
                    self.whitelist = [x for x in self.whitelist
                                      if x not in b_to_rem]

        # take care of important entries first
        if (not Bcfg2.Options.setup.dry_run or
                Bcfg2.Options.setup.only_important):
            important_installs = set()
            for parent in self.config.findall(".//Path/.."):
                name = parent.get("name")
                if not name or (name in Bcfg2.Options.setup.except_bundles and
                                name not in Bcfg2.Options.setup.only_bundles):
                    continue
                for cfile in parent.findall("./Path"):
                    if (cfile.get('name') not in self.__important__ or
                            cfile.get('type') != 'file' or
                            cfile not in self.whitelist):
                        continue
                    tools = [t for t in self.tools
                             if t.handlesEntry(cfile) and t.canVerify(cfile)]
                    if not tools:
                        continue
                    if Bcfg2.Options.setup.dry_run:
                        important_installs.add(cfile)
                        continue
                    if (Bcfg2.Options.setup.interactive and not
                            self.promptFilter("Install %s: %s? (y/N):",
                                              [cfile])):
                        self.whitelist.remove(cfile)
                        continue
                    try:
                        self.states[cfile] = tools[0].InstallPath(cfile)
                        if self.states[cfile]:
                            tools[0].modified.append(cfile)
                    except:  # pylint: disable=W0702
                        self.logger.error("Unexpected tool failure",
                                          exc_info=1)
                    cfile.set('qtext', '')
                    if tools[0].VerifyPath(cfile, []):
                        self.whitelist.remove(cfile)
            if Bcfg2.Options.setup.dry_run and len(important_installs) > 0:
                self.logger.info("In dryrun mode: "
                                 "suppressing entry installation for:")
                self.logger.info(["%s:%s" % (e.tag, e.get('name'))
                                  for e in important_installs])

    def Inventory(self):
        """
           Verify all entries,
           find extra entries,
           and build up workqueues

        """
        # initialize all states
        for struct in self.config.getchildren():
            for entry in struct.getchildren():
                self.states[entry] = False
        for tool in self.tools:
            try:
                self.states.update(tool.Inventory())
            except KeyboardInterrupt:
                raise
            except:  # pylint: disable=W0702
                self.logger.error("%s.Inventory() call failed:" % tool.name,
                                  exc_info=1)

    def Decide(self):  # pylint: disable=R0912
        """Set self.whitelist based on user interaction."""
        iprompt = "Install %s: %s? (y/N): "
        rprompt = "Remove %s: %s? (y/N): "
        if Bcfg2.Options.setup.remove:
            if Bcfg2.Options.setup.remove == 'all':
                self.removal = self.extra
            elif Bcfg2.Options.setup.remove == 'services':
                self.removal = [entry for entry in self.extra
                                if entry.tag == 'Service']
            elif Bcfg2.Options.setup.remove == 'packages':
                self.removal = [entry for entry in self.extra
                                if entry.tag == 'Package']
            elif Bcfg2.Options.setup.remove == 'users':
                self.removal = [entry for entry in self.extra
                                if entry.tag in ['POSIXUser', 'POSIXGroup']]

        candidates = [entry for entry in self.states
                      if not self.states[entry]]

        if Bcfg2.Options.setup.dry_run:
            if self.whitelist:
                self.logger.info("In dryrun mode: "
                                 "suppressing entry installation for:")
                self.logger.info(["%s:%s" % (entry.tag, entry.get('name'))
                                  for entry in self.whitelist])
                self.whitelist = []
            if self.removal:
                self.logger.info("In dryrun mode: "
                                 "suppressing entry removal for:")
                self.logger.info(["%s:%s" % (entry.tag, entry.get('name'))
                                  for entry in self.removal])
            self.removal = []

        # Here is where most of the work goes
        # first perform bundle filtering
        all_bundle_names = [b.get('name')
                            for b in self.config.findall('./Bundle')]
        bundles = self.config.getchildren()
        if Bcfg2.Options.setup.only_bundles:
            # warn if non-existent bundle given
            for bundle in Bcfg2.Options.setup.only_bundles:
                if bundle not in all_bundle_names:
                    self.logger.info("Warning: Bundle %s not found" % bundle)
            bundles = [b for b in bundles
                       if b.get('name') in Bcfg2.Options.setup.only_bundles]
        if Bcfg2.Options.setup.except_bundles:
            # warn if non-existent bundle given
            if not Bcfg2.Options.setup.bundle_quick:
                for bundle in Bcfg2.Options.setup.except_bundles:
                    if bundle not in all_bundle_names:
                        self.logger.info("Warning: Bundle %s not found" %
                                         bundle)
            bundles = [
                b for b in bundles
                if b.get('name') not in Bcfg2.Options.setup.except_bundles]
        self.whitelist = [e for e in self.whitelist
                          if any(e in b for b in bundles)]

        # first process prereq actions
        for bundle in bundles[:]:
            if bundle.tag == 'Bundle':
                bmodified = any((item in self.whitelist or
                                 item in self.modified) for item in bundle)
            else:
                bmodified = False
            actions = [a for a in bundle.findall('./Action')
                       if (a.get('timing') in ['pre', 'both'] and
                           (bmodified or a.get('when') == 'always'))]
            # now we process all "pre" and "both" actions that are either
            # always or the bundle has been modified
            if Bcfg2.Options.setup.interactive:
                self.promptFilter(iprompt, actions)
            self.DispatchInstallCalls(actions)

            if bundle.tag != 'Bundle':
                continue

            # need to test to fail entries in whitelist
            if not all(self.states[a] for a in actions):
                # then display bundles forced off with entries
                self.logger.info("%s %s failed prerequisite action" %
                                 (bundle.tag, bundle.get('name')))
                bundles.remove(bundle)
                b_to_remv = [ent for ent in self.whitelist if ent in bundle]
                if b_to_remv:
                    self.logger.info("Not installing entries from %s %s" %
                                     (bundle.tag, bundle.get('name')))
                    self.logger.info(["%s:%s" % (e.tag, e.get('name'))
                                      for e in b_to_remv])
                    for ent in b_to_remv:
                        self.whitelist.remove(ent)

        self.logger.debug("Installing entries in the following bundle(s):")
        self.logger.debug("  %s" % ", ".join(b.get("name") for b in bundles
                                             if b.get("name")))

        if Bcfg2.Options.setup.interactive:
            self.whitelist = self.promptFilter(iprompt, self.whitelist)
            self.removal = self.promptFilter(rprompt, self.removal)

        for entry in candidates:
            if entry not in self.whitelist:
                self.blacklist.append(entry)

    def DispatchInstallCalls(self, entries):
        """Dispatch install calls to underlying tools."""
        for tool in self.tools:
            handled = [entry for entry in entries if tool.canInstall(entry)]
            if not handled:
                continue
            try:
                self.states.update(tool.Install(handled))
            except KeyboardInterrupt:
                raise
            except:  # pylint: disable=W0702
                self.logger.error("%s.Install() call failed:" % tool.name,
                                  exc_info=1)

    def Install(self):
        """Install all entries."""
        self.DispatchInstallCalls(self.whitelist)
        mods = self.modified
        mbundles = [struct for struct in self.config.findall('Bundle')
                    if any(True for mod in mods if mod in struct)]

        if self.modified:
            # Handle Bundle interdeps
            if mbundles:
                self.logger.info("The Following Bundles have been modified:")
                self.logger.info([mbun.get('name') for mbun in mbundles])
            tbm = [(t, b) for t in self.tools for b in mbundles]
            for tool, bundle in tbm:
                try:
                    self.states.update(tool.Inventory(structures=[bundle]))
                except KeyboardInterrupt:
                    raise
                except:  # pylint: disable=W0702
                    self.logger.error("%s.Inventory() call failed:" %
                                      tool.name,
                                      exc_info=1)
            clobbered = [entry for bundle in mbundles for entry in bundle
                         if (not self.states[entry] and
                             entry not in self.blacklist)]
            if clobbered:
                self.logger.debug("Found clobbered entries:")
                self.logger.debug(["%s:%s" % (entry.tag, entry.get('name'))
                                   for entry in clobbered])
                if not Bcfg2.Options.setup.interactive:
                    self.DispatchInstallCalls(clobbered)

        all_bundles = self.config.findall('./Bundle')
        mbundles.extend(self._get_all_modified_bundles(mbundles, all_bundles))

        for bundle in all_bundles:
            if (Bcfg2.Options.setup.only_bundles and
                    bundle.get('name') not in
                    Bcfg2.Options.setup.only_bundles):
                # prune out unspecified bundles when running with -b
                continue
            if bundle in mbundles:
                continue

            self.logger.debug("Bundle %s was not modified" %
                              bundle.get('name'))
            for tool in self.tools:
                try:
                    self.states.update(tool.BundleNotUpdated(bundle))
                except KeyboardInterrupt:
                    raise
                except:  # pylint: disable=W0702
                    self.logger.error('%s.BundleNotUpdated(%s:%s) call failed:'
                                      % (tool.name, bundle.tag,
                                         bundle.get('name')), exc_info=1)

        for indep in self.config.findall('.//Independent'):
            for tool in self.tools:
                try:
                    self.states.update(tool.BundleNotUpdated(indep))
                except KeyboardInterrupt:
                    raise
                except:  # pylint: disable=W0702
                    self.logger.error("%s.BundleNotUpdated(%s:%s) call failed:"
                                      % (tool.name, indep.tag,
                                         indep.get("name")), exc_info=1)

    def _get_all_modified_bundles(self, mbundles, all_bundles):
        """This gets all modified bundles by calling BundleUpdated until no
        new bundles get added to the modification list."""
        new_mbundles = mbundles
        add_mbundles = []

        while new_mbundles:
            for bundle in self.config.findall('./Bundle'):
                if (Bcfg2.Options.setup.only_bundles and
                        bundle.get('name') not in
                        Bcfg2.Options.setup.only_bundles):
                    # prune out unspecified bundles when running with -b
                    continue
                if bundle not in new_mbundles:
                    continue

                self.logger.debug('Bundle %s was modified' %
                                  bundle.get('name'))
                for tool in self.tools:
                    try:
                        self.states.update(tool.BundleUpdated(bundle))
                    except:  # pylint: disable=W0702
                        self.logger.error('%s.BundleUpdated(%s:%s) call '
                                          'failed:' % (tool.name, bundle.tag,
                                                       bundle.get("name")),
                                          exc_info=1)

            mods = self.modified
            new_mbundles = [struct for struct in all_bundles
                            if any(True for mod in mods if mod in struct) and
                            struct not in mbundles + add_mbundles]
            add_mbundles.extend(new_mbundles)

        return add_mbundles

    def Remove(self):
        """Remove extra entries."""
        for tool in self.tools:
            extras = [entry for entry in self.removal
                      if tool.handlesEntry(entry)]
            if extras:
                try:
                    tool.Remove(extras)
                except:  # pylint: disable=W0702
                    self.logger.error("%s.Remove() failed" % tool.name,
                                      exc_info=1)

    def CondDisplayState(self, phase):
        """Conditionally print tracing information."""
        self.logger.info('Phase: %s' % phase)
        self.logger.info('Correct entries:        %d' %
                         list(self.states.values()).count(True))
        self.logger.info('Incorrect entries:      %d' %
                         list(self.states.values()).count(False))
        if phase == 'final' and list(self.states.values()).count(False):
            for entry in sorted(self.states.keys(), key=lambda e: e.tag + ":" +
                                e.get('name')):
                if not self.states[entry]:
                    etype = entry.get('type')
                    if etype:
                        self.logger.info("%s:%s:%s" % (entry.tag, etype,
                                                       entry.get('name')))
                    else:
                        self.logger.info("%s:%s" % (entry.tag,
                                                    entry.get('name')))
        self.logger.info('Total managed entries: %d' %
                         len(list(self.states.values())))
        self.logger.info('Unmanaged entries:      %d' % len(self.extra))
        if phase == 'final' and Bcfg2.Options.setup.show_extra:
            for entry in sorted(self.extra,
                                key=lambda e: e.tag + ":" + e.get('name')):
                etype = entry.get('type')
                if etype:
                    self.logger.info("%s:%s:%s" % (entry.tag, etype,
                                                   entry.get('name')))
                else:
                    self.logger.info("%s:%s" % (entry.tag,
                                                entry.get('name')))

        if ((list(self.states.values()).count(False) == 0) and not self.extra):
            self.logger.info('All entries correct.')

    def ReInventory(self):
        """Recheck everything."""
        if not Bcfg2.Options.setup.dry_run and Bcfg2.Options.setup.kevlar:
            self.logger.info("Rechecking system inventory")
            self.Inventory()

    def Execute(self):
        """Run all methods."""
        self.Inventory()
        self.times['inventory'] = time.time()
        self.CondDisplayState('initial')
        self.InstallImportant()
        if not Bcfg2.Options.setup.only_important:
            self.Decide()
            self.Install()
            self.times['install'] = time.time()
            self.Remove()
            self.times['remove'] = time.time()

        if self.modified:
            self.ReInventory()
            self.times['reinventory'] = time.time()
        self.times['finished'] = time.time()
        self.CondDisplayState('final')

    def GenerateStats(self):
        """Generate XML summary of execution statistics."""
        states = {}
        for (item, val) in list(self.states.items()):
            if not Bcfg2.Options.setup.only_important or \
               item.get('important', 'false').lower() == 'true':
                states[item] = val

        feedback = XML.Element("upload-statistics")
        stats = XML.SubElement(feedback,
                               'Statistics', total=str(len(states)),
                               version='2.0',
                               revision=self.config.get('revision', '-1'))
        flags = XML.SubElement(stats, "Flags")
        XML.SubElement(flags, "Flag", name="dry_run",
                       value=str(Bcfg2.Options.setup.dry_run))
        XML.SubElement(flags, "Flag", name="only_important",
                       value=str(Bcfg2.Options.setup.only_important))
        good_entries = [key for key, val in list(states.items()) if val]
        good = len(good_entries)
        stats.set('good', str(good))
        if any(not val for val in list(states.values())):
            stats.set('state', 'dirty')
        else:
            stats.set('state', 'clean')

        # List bad elements of the configuration
        for (data, ename) in [(self.modified, 'Modified'),
                              (self.extra, "Extra"),
                              (good_entries, "Good"),
                              ([entry for entry in states
                                if not states[entry]], "Bad")]:
            container = XML.SubElement(stats, ename)
            for item in data:
                item.set('qtext', '')
                container.append(item)
                item.text = None

        timeinfo = XML.Element("OpStamps")
        feedback.append(stats)
        for (event, timestamp) in list(self.times.items()):
            timeinfo.set(event, str(timestamp))
        stats.append(timeinfo)
        return feedback
