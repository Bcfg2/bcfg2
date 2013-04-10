""" The main Bcfg2 client class """

import os
import sys
import stat
import time
import fcntl
import socket
import logging
import tempfile
import Bcfg2.Proxy
import Bcfg2.Logger
import Bcfg2.Options
import Bcfg2.Client.XML
import Bcfg2.Client.Frame
import Bcfg2.Client.Tools
from Bcfg2.Utils import locked, Executor
from Bcfg2.Compat import xmlrpclib
from Bcfg2.version import __version__


class Client(object):
    """ The main Bcfg2 client class """

    def __init__(self, setup):
        self.toolset = None
        self.tools = None
        self.config = None
        self._proxy = None
        self.setup = setup

        if self.setup['debug']:
            level = logging.DEBUG
        elif self.setup['verbose']:
            level = logging.INFO
        else:
            level = logging.WARNING
        Bcfg2.Logger.setup_logging('bcfg2',
                                   to_syslog=self.setup['syslog'],
                                   level=level,
                                   to_file=self.setup['logging'])
        self.logger = logging.getLogger('bcfg2')
        self.logger.debug(self.setup)

        self.cmd = Executor(self.setup['command_timeout'])

        if self.setup['bundle_quick']:
            if not self.setup['bundle'] and not self.setup['skipbundle']:
                self.logger.error("-Q option requires -b or -B")
                raise SystemExit(1)
            elif self.setup['remove']:
                self.logger.error("-Q option incompatible with -r")
                raise SystemExit(1)
        if 'drivers' in self.setup and self.setup['drivers'] == 'help':
            self.logger.info("The following drivers are available:")
            self.logger.info(Bcfg2.Client.Tools.drivers)
            raise SystemExit(0)
        if self.setup['remove'] and 'services' in self.setup['remove'].lower():
            self.logger.error("Service removal is nonsensical; "
                              "removed services will only be disabled")
        if (self.setup['remove'] and
            self.setup['remove'].lower() not in ['all', 'services', 'packages',
                                                 'users']):
            self.logger.error("Got unknown argument %s for -r" %
                              self.setup['remove'])
        if self.setup["file"] and self.setup["cache"]:
            print("cannot use -f and -c together")
            raise SystemExit(1)
        if not self.setup['server'].startswith('https://'):
            self.setup['server'] = 'https://' + self.setup['server']

    def _probe_failure(self, probename, msg):
        """ handle failure of a probe in the way the user wants us to
        (exit or continue) """
        message = "Failed to execute probe %s: %s" % (probename, msg)
        if self.setup['probe_exit']:
            self.fatal_error(message)
        else:
            self.logger.error(message)

    def run_probe(self, probe):
        """Execute probe."""
        name = probe.get('name')
        self.logger.info("Running probe %s" % name)
        ret = Bcfg2.Client.XML.Element("probe-data",
                                       name=name,
                                       source=probe.get('source'))
        try:
            scripthandle, scriptname = tempfile.mkstemp()
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
                rv = self.cmd.run(scriptname, timeout=self.setup['timeout'])
                if rv.stderr:
                    self.logger.warning("Probe %s has error output: %s" %
                                        (name, rv.stderr))
                if not rv.success:
                    self._probe_failure(name, "Return value %s" % rv)
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
            self._proxy = Bcfg2.Proxy.ComponentProxy(
                self.setup['server'],
                self.setup['user'],
                self.setup['password'],
                key=self.setup['key'],
                cert=self.setup['certificate'],
                ca=self.setup['ca'],
                allowedServerCNs=self.setup['serverCN'],
                timeout=self.setup['timeout'],
                retries=int(self.setup['retries']),
                delay=int(self.setup['retry_delay']))
        return self._proxy

    def run_probes(self, times=None):
        """ run probes and upload probe data """
        if times is None:
            times = dict()

        try:
            probes = Bcfg2.Client.XML.XML(str(self.proxy.GetProbes()))
        except (Bcfg2.Proxy.ProxyError,
                Bcfg2.Proxy.CertificateError,
                socket.gaierror,
                socket.error):
            err = sys.exc_info()[1]
            self.fatal_error("Failed to download probes from bcfg2: %s" % err)
        except Bcfg2.Client.XML.ParseError:
            err = sys.exc_info()[1]
            self.fatal_error("Server returned invalid probe requests: %s" %
                             err)

        times['probe_download'] = time.time()

        # execute probes
        probedata = Bcfg2.Client.XML.Element("ProbeData")
        for probe in probes.findall(".//probe"):
            probedata.append(self.run_probe(probe))

        if len(probes.findall(".//probe")) > 0:
            try:
                # upload probe responses
                self.proxy.RecvProbeData(
                    Bcfg2.Client.XML.tostring(
                        probedata,
                        xml_declaration=False).decode('utf-8'))
            except Bcfg2.Proxy.ProxyError:
                err = sys.exc_info()[1]
                self.fatal_error("Failed to upload probe data: %s" % err)

        times['probe_upload'] = time.time()

    def get_config(self, times=None):
        """ load the configuration, either from the cached
        configuration file (-f), or from the server """
        if times is None:
            times = dict()

        if self.setup['file']:
            # read config from file
            try:
                self.logger.debug("Reading cached configuration from %s" %
                                  self.setup['file'])
                return open(self.setup['file'], 'r').read()
            except IOError:
                self.fatal_error("Failed to read cached configuration from: %s"
                                 % (self.setup['file']))
        else:
            # retrieve config from server
            if self.setup['profile']:
                try:
                    self.proxy.AssertProfile(self.setup['profile'])
                except Bcfg2.Proxy.ProxyError:
                    err = sys.exc_info()[1]
                    self.fatal_error("Failed to set client profile: %s" % err)

            try:
                self.proxy.DeclareVersion(__version__)
            except xmlrpclib.Fault:
                err = sys.exc_info()[1]
                if (err.faultCode == xmlrpclib.METHOD_NOT_FOUND or
                    (err.faultCode == 7 and
                     err.faultString.startswith("Unknown method"))):
                    self.logger.debug("Server does not support declaring "
                                      "client version")
                else:
                    self.logger.error("Failed to declare version: %s" % err)
            except (Bcfg2.Proxy.ProxyError,
                    Bcfg2.Proxy.CertificateError,
                    socket.gaierror,
                    socket.error):
                err = sys.exc_info()[1]
                self.logger.error("Failed to declare version: %s" % err)

            self.run_probes(times=times)

            if self.setup['decision'] in ['whitelist', 'blacklist']:
                try:
                    self.setup['decision_list'] = \
                        self.proxy.GetDecisionList(self.setup['decision'])
                    self.logger.info("Got decision list from server:")
                    self.logger.info(self.setup['decision_list'])
                except Bcfg2.Proxy.ProxyError:
                    err = sys.exc_info()[1]
                    self.fatal_error("Failed to get decision list: %s" % err)

            try:
                rawconfig = self.proxy.GetConfig().encode('utf-8')
            except Bcfg2.Proxy.ProxyError:
                err = sys.exc_info()[1]
                self.fatal_error("Failed to download configuration from "
                                 "Bcfg2: %s" % err)

            times['config_download'] = time.time()
        return rawconfig

    def run(self):
        """Perform client execution phase."""
        times = {}

        # begin configuration
        times['start'] = time.time()

        self.logger.info("Starting Bcfg2 client run at %s" % times['start'])

        rawconfig = self.get_config(times=times).decode('utf-8')

        if self.setup['cache']:
            try:
                open(self.setup['cache'], 'w').write(rawconfig)
                os.chmod(self.setup['cache'], 33152)
            except IOError:
                self.logger.warning("Failed to write config cache file %s" %
                                    (self.setup['cache']))
            times['caching'] = time.time()

        try:
            self.config = Bcfg2.Client.XML.XML(rawconfig)
        except Bcfg2.Client.XML.ParseError:
            syntax_error = sys.exc_info()[1]
            self.fatal_error("The configuration could not be parsed: %s" %
                             syntax_error)

        times['config_parse'] = time.time()

        if self.config.tag == 'error':
            self.fatal_error("Server error: %s" % (self.config.text))
            return(1)

        if self.setup['bundle_quick']:
            newconfig = Bcfg2.Client.XML.XML('<Configuration/>')
            for bundle in self.config.getchildren():
                if (bundle.tag == 'Bundle' and
                    ((self.setup['bundle'] and
                      bundle.get('name') in self.setup['bundle']) or
                     (self.setup['skipbundle'] and
                      bundle.get('name') not in self.setup['skipbundle']))):
                    newconfig.append(bundle)
            self.config = newconfig

        self.tools = Bcfg2.Client.Frame.Frame(self.config,
                                              self.setup,
                                              times, self.setup['drivers'],
                                              self.setup['dryrun'])

        if not self.setup['omit_lock_check']:
            #check lock here
            try:
                lockfile = open(self.setup['lockfile'], 'w')
                if locked(lockfile.fileno()):
                    self.fatal_error("Another instance of Bcfg2 is running. "
                                     "If you want to bypass the check, run "
                                     "with the %s option" %
                                     Bcfg2.Options.OMIT_LOCK_CHECK.cmd)
            except SystemExit:
                raise
            except:
                lockfile = None
                self.logger.error("Failed to open lockfile %s: %s" %
                                  (self.setup['lockfile'], sys.exc_info()[1]))

        # execute the configuration
        self.tools.Execute()

        if not self.setup['omit_lock_check']:
            # unlock here
            if lockfile:
                try:
                    fcntl.lockf(lockfile.fileno(), fcntl.LOCK_UN)
                    os.remove(self.setup['lockfile'])
                except OSError:
                    self.logger.error("Failed to unlock lockfile %s" %
                                      lockfile.name)

        if not self.setup['file'] and not self.setup['bundle_quick']:
            # upload statistics
            feedback = self.tools.GenerateStats()

            try:
                self.proxy.RecvStats(
                    Bcfg2.Client.XML.tostring(
                        feedback,
                        xml_declaration=False).decode('utf-8'))
            except Bcfg2.Proxy.ProxyError:
                err = sys.exc_info()[1]
                self.logger.error("Failed to upload configuration statistics: "
                                  "%s" % err)
                raise SystemExit(2)

        self.logger.info("Finished Bcfg2 client run at %s" % time.time())
