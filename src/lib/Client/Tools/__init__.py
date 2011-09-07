"""This contains all Bcfg2 Tool modules"""
# suppress popen2 warnings for python 2.3
import warnings
warnings.filterwarnings("ignore", "The popen2 module is deprecated.*",
                        DeprecationWarning)
import os
import stat
import sys
from subprocess import Popen, PIPE
import time

import Bcfg2.Client.XML
__revision__ = '$Revision$'

__all__ = [tool.split('.')[0] \
           for tool in os.listdir(os.path.dirname(__file__)) \
           if tool.endswith(".py") and tool != "__init__.py"]

drivers = [item for item in __all__ if item not in ['rpmtools']]
default = [item for item in drivers if item not in ['RPM', 'Yum']]


class toolInstantiationError(Exception):
    """This error is called if the toolset cannot be instantiated."""
    pass


class executor:
    """This class runs stuff for us"""

    def __init__(self, logger):
        self.logger = logger

    def run(self, command):
        """Run a command in a pipe dealing with stdout buffer overloads."""
        p = Popen(command, shell=True, bufsize=16384,
                  stdin=PIPE, stdout=PIPE, close_fds=True)
        output = p.communicate()[0]
        for line in output.splitlines():
            self.logger.debug('< %s' % line)
        return (p.returncode, output.splitlines())


class Tool:
    """
    All tools subclass this. It defines all interfaces that need to be defined.
    """
    name = 'Tool'
    __execs__ = []
    __handles__ = []
    __req__ = {}
    __important__ = []

    def __init__(self, logger, setup, config):
        self.__important__ = [entry.get('name') \
                              for struct in config for entry in struct \
                              if entry.tag == 'Path' and \
                              entry.get('important') in ['true', 'True']]
        self.setup = setup
        self.logger = logger
        if not hasattr(self, '__ireq__'):
            self.__ireq__ = self.__req__
        self.config = config
        self.cmd = executor(logger)
        self.modified = []
        self.extra = []
        self.handled = [entry for struct in self.config for entry in struct \
                        if self.handlesEntry(entry)]
        for filename in self.__execs__:
            try:
                mode = stat.S_IMODE(os.stat(filename)[stat.ST_MODE])
                if mode & stat.S_IEXEC != stat.S_IEXEC:
                    self.logger.debug("%s: %s not executable" % \
                                      (self.name, filename))
                    raise toolInstantiationError
            except OSError:
                raise toolInstantiationError
            except:
                self.logger.debug("%s failed" % filename, exc_info=1)
                raise toolInstantiationError

    def BundleUpdated(self, _, states):
        """This callback is used when bundle updates occur."""
        return

    def BundleNotUpdated(self, _, states):
        """This callback is used when a bundle is not updated."""
        return

    def Inventory(self, states, structures=[]):
        """Dispatch verify calls to underlying methods."""
        if not structures:
            structures = self.config.getchildren()
        mods = self.buildModlist()
        for (struct, entry) in [(struct, entry) for struct in structures \
                                for entry in struct.getchildren() \
                                if self.canVerify(entry)]:
            try:
                func = getattr(self, "Verify%s" % (entry.tag))
                states[entry] = func(entry, mods)
            except:
                self.logger.error(
                    "Unexpected failure of verification method for entry type %s" \
                    % (entry.tag), exc_info=1)
        self.extra = self.FindExtra()

    def Install(self, entries, states):
        """Install all entries in sublist."""
        for entry in entries:
            try:
                func = getattr(self, "Install%s" % (entry.tag))
                states[entry] = func(entry)
                if states[entry]:
                    self.modified.append(entry)
            except:
                self.logger.error("Unexpected failure of install method for entry type %s" \
                                  % (entry.tag), exc_info=1)

    def Remove(self, entries):
        """Remove specified extra entries"""
        pass

    def getSupportedEntries(self):
        """Return a list of supported entries."""
        return [entry for struct in \
                self.config.getchildren() for entry in \
                struct.getchildren() \
                if self.handlesEntry(entry)]

    def handlesEntry(self, entry):
        """Return if entry is handled by this tool."""
        return (entry.tag, entry.get('type')) in self.__handles__

    def buildModlist(self):
        '''Build a list of potentially modified POSIX paths for this entry'''
        return [entry.get('name') for struct in self.config.getchildren() \
                for entry in struct.getchildren() \
                if entry.tag in ['Ignore', 'Path']]

    def gatherCurrentData(self, entry):
        """Default implementation of the information gathering routines."""
        pass

    def canVerify(self, entry):
        """Test if entry has enough information to be verified."""
        if not self.handlesEntry(entry):
            return False

        if 'failure' in entry.attrib:
            self.logger.error("Entry %s:%s reports bind failure: %s" % \
                              (entry.tag,
                               entry.get('name'),
                               entry.get('failure')))
            return False

        missing = [attr for attr in self.__req__[entry.tag] \
                   if attr not in entry.attrib]
        if missing:
            self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                              % (entry.tag, entry.get('name')))
            self.logger.error("\t... due to absence of %s attribute(s)" % \
                              (":".join(missing)))
            try:
                self.gatherCurrentData(entry)
            except:
                self.logger.error("Unexpected error in gatherCurrentData",
                                  exc_info=1)
            return False
        return True

    def FindExtra(self):
        """Return a list of extra entries."""
        return []

    def canInstall(self, entry):
        """Test if entry has enough information to be installed."""
        if not self.handlesEntry(entry):
            return False

        if 'failure' in entry.attrib:
            self.logger.error("Cannot install entry %s:%s with bind failure" % \
                              (entry.tag, entry.get('name')))
            return False

        missing = [attr for attr in self.__ireq__[entry.tag] \
                   if attr not in entry.attrib or not entry.attrib[attr]]
        if missing:
            self.logger.error("Incomplete information for entry %s:%s; cannot install" \
                              % (entry.tag, entry.get('name')))
            self.logger.error("\t... due to absence of %s attribute" % \
                              (":".join(missing)))
            return False
        return True


class PkgTool(Tool):
    """
       PkgTool provides a one-pass install with
       fallback for use with packaging systems
    """
    pkgtool = ('echo %s', ('%s', ['name']))
    pkgtype = 'echo'
    name = 'PkgTool'

    def __init__(self, logger, setup, config):
        Tool.__init__(self, logger, setup, config)
        self.installed = {}
        self.Remove = self.RemovePackages
        self.FindExtra = self.FindExtraPackages
        self.RefreshPackages()

    def VerifyPackage(self, dummy, _):
        """Dummy verification method"""
        return False

    def Install(self, packages, states):
        """
           Run a one-pass install, followed by
           single pkg installs in case of failure.
        """
        self.logger.info("Trying single pass package install for pkgtype %s" % \
                         self.pkgtype)

        data = [tuple([pkg.get(field) for field in self.pkgtool[1][1]])
                for pkg in packages]
        pkgargs = " ".join([self.pkgtool[1][0] % datum for datum in data])

        self.logger.debug("Installing packages: :%s:" % pkgargs)
        self.logger.debug("Running command ::%s::" % (self.pkgtool[0] % pkgargs))

        cmdrc = self.cmd.run(self.pkgtool[0] % pkgargs)[0]
        if cmdrc == 0:
            self.logger.info("Single Pass Succeded")
            # set all package states to true and flush workqueues
            pkgnames = [pkg.get('name') for pkg in packages]
            for entry in [entry for entry in list(states.keys())
                          if entry.tag == 'Package'
                          and entry.get('type') == self.pkgtype
                          and entry.get('name') in pkgnames]:
                self.logger.debug('Setting state to true for pkg %s' % \
                                  (entry.get('name')))
                states[entry] = True
            self.RefreshPackages()
        else:
            self.logger.error("Single Pass Failed")
            # do single pass installs
            self.RefreshPackages()
            for pkg in packages:
                # handle state tracking updates
                if self.VerifyPackage(pkg, []):
                    self.logger.info("Forcing state to true for pkg %s" % \
                                     (pkg.get('name')))
                    states[pkg] = True
                else:
                    self.logger.info("Installing pkg %s version %s" %
                                     (pkg.get('name'), pkg.get('version')))
                    cmdrc = self.cmd.run(self.pkgtool[0] %
                                         (self.pkgtool[1][0] %
                                          tuple([pkg.get(field) for field in self.pkgtool[1][1]])))
                    if cmdrc[0] == 0:
                        states[pkg] = True
                    else:
                        self.logger.error("Failed to install package %s" % \
                                          (pkg.get('name')))
            self.RefreshPackages()
        for entry in [ent for ent in packages if states[ent]]:
            self.modified.append(entry)

    def RefreshPackages(self):
        """Dummy state refresh method."""
        pass

    def RemovePackages(self, packages):
        """Dummy implementation of package removal method."""
        pass

    def FindExtraPackages(self):
        """Find extra packages."""
        packages = [entry.get('name') for entry in self.getSupportedEntries()]
        extras = [data for data in list(self.installed.items()) \
                  if data[0] not in packages]
        return [Bcfg2.Client.XML.Element('Package', name=name, \
                                         type=self.pkgtype, version=version) \
                                         for (name, version) in extras]


class SvcTool(Tool):
    """This class defines basic Service behavior"""
    name = 'SvcTool'

    def get_svc_command(self, service, action):
        """Return the basename of the command used to start/stop services."""
        return '/etc/init.d/%s %s' % (service.get('name'), action)

    def start_service(self, service):
        self.logger.debug('Starting service %s' % service.get('name'))
        return self.cmd.run(self.get_svc_command(service, 'start'))[0]

    def stop_service(self, service):
        self.logger.debug('Stopping service %s' % service.get('name'))
        return self.cmd.run(self.get_svc_command(service, 'stop'))[0]

    def restart_service(self, service):
        self.logger.debug('Restarting service %s' % service.get('name'))
        restart_target = service.get('target', 'restart')
        return self.cmd.run(self.get_svc_command(service, restart_target))[0]

    def check_service(self, service):
        # not supported for this driver
        return 0

    def BundleUpdated(self, bundle, states):
        """The Bundle has been updated."""
        if self.setup['servicemode'] == 'disabled':
            return

        for entry in [ent for ent in bundle if self.handlesEntry(ent)]:
            mode = entry.get('mode', 'default')
            if mode == 'manual' or \
                    (mode == 'interactive_only' and not self.setup['interactive']):
                continue
            # need to handle servicemode = (build|default)
            # need to handle mode = (default|supervised)
            if entry.get('status') == 'on':
                if self.setup['servicemode'] == 'build':
                    rc = self.stop_service(entry)
                else:
                    if self.setup['interactive']:
                        prompt = 'Restart service %s?: (y/N): ' % entry.get('name')
                        # py3k compatibility
                        try:
                            ans = raw_input(prompt)
                        except NameError:
                            ans = input(prompt)
                        if ans not in ['y', 'Y']:
                            continue
                    rc = self.restart_service(entry)
            else:
                rc = self.stop_service(entry)
            if rc:
                self.logger.error("Failed to manipulate service %s" % \
                                  (entry.get('name')))
