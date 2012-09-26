"""This contains all Bcfg2 Tool modules"""

import os
import stat
from subprocess import Popen, PIPE
import Bcfg2.Client.XML
from Bcfg2.Compat import input, walk_packages  # pylint: disable=W0622

__all__ = [m[1] for m in walk_packages(path=__path__)]

# pylint: disable=C0103
drivers = [item for item in __all__ if item not in ['rpmtools']]
default = drivers[:]
# pylint: enable=C0103


class ToolInstantiationError(Exception):
    """This error is called if the toolset cannot be instantiated."""
    pass


class Executor:
    """This class runs stuff for us"""

    def __init__(self, logger):
        self.logger = logger

    def run(self, command):
        """Run a command in a pipe dealing with stdout buffer overloads."""
        proc = Popen(command, shell=True, bufsize=16384,
                     stdin=PIPE, stdout=PIPE, close_fds=True)
        output = proc.communicate()[0]
        for line in output.splitlines():
            self.logger.debug('< %s' % line)
        return (proc.returncode, output.splitlines())


class ClassName(object):
    """ This very simple descriptor class exists only to get the name
    of the owner class.  This is used because, for historical reasons,
    we expect every tool to have a ``name`` attribute that is in
    almost all cases the same as the ``__class__.__name__`` attribute
    of the plugin object.  This makes that more dynamic so that each
    plugin isn't repeating its own name."""

    def __get__(self, inst, owner):
        return owner.__name__


# pylint: disable=W0702
# in the base tool class we frequently want to catch all exceptions,
# regardless of type, so disable the pylint rule that catches that.
class Tool(object):
    """ All tools subclass this. It defines all interfaces that need
    to be defined. """
    name = ClassName()
    __execs__ = []
    __handles__ = []
    __req__ = {}
    __important__ = []
    deprecated = False

    def __init__(self, logger, setup, config):
        self.setup = setup
        self.logger = logger
        if not hasattr(self, '__ireq__'):
            self.__ireq__ = self.__req__
        self.config = config
        self.cmd = Executor(logger)
        self.modified = []
        self.extra = []
        self.__important__ = []
        self.handled = []
        for struct in config:
            for entry in struct:
                if (entry.tag == 'Path' and
                    entry.get('important', 'false').lower() == 'true'):
                    self.__important__.append(entry.get('name'))
                if self.handlesEntry(entry):
                    self.handled.append(entry)
        for filename in self.__execs__:
            try:
                mode = stat.S_IMODE(os.stat(filename)[stat.ST_MODE])
                if mode & stat.S_IEXEC != stat.S_IEXEC:
                    self.logger.debug("%s: %s not executable" %
                                      (self.name, filename))
                    raise ToolInstantiationError
            except OSError:
                raise ToolInstantiationError
            except:
                self.logger.debug("%s failed" % filename, exc_info=1)
                raise ToolInstantiationError

    def BundleUpdated(self, bundle, states):  # pylint: disable=W0613
        """This callback is used when bundle updates occur."""
        return

    def BundleNotUpdated(self, bundle, states):  # pylint: disable=W0613
        """This callback is used when a bundle is not updated."""
        return

    def Inventory(self, states, structures=None):
        """Dispatch verify calls to underlying methods."""
        if not structures:
            structures = self.config.getchildren()
        mods = self.buildModlist()
        for struct in structures:
            for entry in struct.getchildren():
                if self.canVerify(entry):
                    try:
                        func = getattr(self, "Verify%s" % entry.tag)
                        states[entry] = func(entry, mods)
                    except:
                        self.logger.error("Unexpected failure of verification "
                                          "method for entry type %s" %
                                          entry.tag, exc_info=1)
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
                self.logger.error("Unexpected failure of install method for "
                                  "entry type %s" % entry.tag,
                                  exc_info=1)

    def Remove(self, entries):
        """Remove specified extra entries"""
        pass

    def getSupportedEntries(self):
        """Return a list of supported entries."""
        rv = []
        for struct in self.config.getchildren():
            rv.extend([entry for entry in struct.getchildren()
                       if self.handlesEntry(entry)])
        return rv

    def handlesEntry(self, entry):
        """Return if entry is handled by this tool."""
        return (entry.tag, entry.get('type')) in self.__handles__

    def buildModlist(self):
        """ Build a list of potentially modified POSIX paths for this
        entry """
        rv = []
        for struct in self.config.getchildren():
            rv.extend([entry.get('name') for entry in struct.getchildren()
                       if entry.tag == 'Path'])
        return rv

    def gatherCurrentData(self, entry):
        """Default implementation of the information gathering routines."""
        pass

    def missing_attrs(self, entry):
        """ Return a list of attributes that were expected on entry
        but not found """
        required = self.__req__[entry.tag]
        if isinstance(required, dict):
            required = ["type"]
            try:
                required.extend(self.__req__[entry.tag][entry.get("type")])
            except KeyError:
                pass

        return [attr for attr in required
                if attr not in entry.attrib or not entry.attrib[attr]]

    def canVerify(self, entry):
        """Test if entry has enough information to be verified."""
        if not self.handlesEntry(entry):
            return False

        if 'failure' in entry.attrib:
            self.logger.error("Entry %s:%s reports bind failure: %s" %
                              (entry.tag, entry.get('name'),
                               entry.get('failure')))
            return False

        missing = self.missing_attrs(entry)
        if missing:
            self.logger.error("Cannot verify entry %s:%s due to missing "
                              "required attribute(s): %s" %
                              (entry.tag, entry.get('name'),
                               ", ".join(missing)))
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

    def primarykey(self, entry):
        """ return a string that should be unique amongst all entries
        in the specification """
        return "%s:%s" % (entry.tag, entry.get("name"))

    def canInstall(self, entry):
        """Test if entry has enough information to be installed."""
        if not self.handlesEntry(entry):
            return False

        if 'failure' in entry.attrib:
            self.logger.error("Cannot install entry %s:%s with bind failure" %
                              (entry.tag, entry.get('name')))
            return False

        missing = self.missing_attrs(entry)
        if missing:
            self.logger.error("Incomplete information for entry %s:%s; cannot "
                              "install due to absence of attribute(s): %s" %
                              (entry.tag, entry.get('name'),
                               ", ".join(missing)))
            return False
        return True
# pylint: enable=W0702


class PkgTool(Tool):
    """ PkgTool provides a one-pass install with fallback for use with
    packaging systems """
    pkgtool = ('echo %s', ('%s', ['name']))
    pkgtype = 'echo'

    def __init__(self, logger, setup, config):
        Tool.__init__(self, logger, setup, config)
        self.installed = {}
        self.RefreshPackages()
        self.Remove = self.RemovePackages  # pylint: disable=C0103
        self.FindExtra = self.FindExtraPackages  # pylint: disable=C0103

    def VerifyPackage(self, dummy, _):
        """Dummy verification method"""
        return False

    def Install(self, packages, states):
        """ Run a one-pass install, followed by single pkg installs in
        case of failure. """
        self.logger.info("Trying single pass package install for pkgtype %s" %
                         self.pkgtype)

        data = [tuple([pkg.get(field) for field in self.pkgtool[1][1]])
                for pkg in packages]
        pkgargs = " ".join([self.pkgtool[1][0] % datum for datum in data])

        self.logger.debug("Installing packages: %s" % pkgargs)
        self.logger.debug("Running command: %s" % (self.pkgtool[0] % pkgargs))

        cmdrc = self.cmd.run(self.pkgtool[0] % pkgargs)[0]
        if cmdrc == 0:
            self.logger.info("Single Pass Succeded")
            # set all package states to true and flush workqueues
            pkgnames = [pkg.get('name') for pkg in packages]
            for entry in list(states.keys()):
                if (entry.tag == 'Package'
                    and entry.get('type') == self.pkgtype
                    and entry.get('name') in pkgnames):
                    self.logger.debug('Setting state to true for pkg %s' %
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
                    self.logger.info("Forcing state to true for pkg %s" %
                                     (pkg.get('name')))
                    states[pkg] = True
                else:
                    self.logger.info("Installing pkg %s version %s" %
                                     (pkg.get('name'), pkg.get('version')))
                    cmdrc = self.cmd.run(
                        self.pkgtool[0] %
                        (self.pkgtool[1][0] %
                         tuple([pkg.get(field)
                                for field in self.pkgtool[1][1]])))
                    if cmdrc[0] == 0:
                        states[pkg] = True
                    else:
                        self.logger.error("Failed to install package %s" %
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
        extras = [data for data in list(self.installed.items())
                  if data[0] not in packages]
        return [Bcfg2.Client.XML.Element('Package', name=name,
                                         type=self.pkgtype, version=version)
                for (name, version) in extras]


class SvcTool(Tool):
    """This class defines basic Service behavior"""

    def __init__(self, logger, setup, config):
        Tool.__init__(self, logger, setup, config)
        self.restarted = []

    def get_svc_command(self, service, action):
        """Return the basename of the command used to start/stop services."""
        return '/etc/init.d/%s %s' % (service.get('name'), action)

    def start_service(self, service):
        """ Start a service """
        self.logger.debug('Starting service %s' % service.get('name'))
        return self.cmd.run(self.get_svc_command(service, 'start'))[0]

    def stop_service(self, service):
        """ Stop a service """
        self.logger.debug('Stopping service %s' % service.get('name'))
        return self.cmd.run(self.get_svc_command(service, 'stop'))[0]

    def restart_service(self, service):
        """ Restart a service """
        self.logger.debug('Restarting service %s' % service.get('name'))
        restart_target = service.get('target', 'restart')
        return self.cmd.run(self.get_svc_command(service, restart_target))[0]

    def check_service(self, service):
        """ Get the status of a service """
        return self.cmd.run(self.get_svc_command(service, 'status'))[0] == 0

    def Remove(self, services):
        """ Dummy implementation of service removal method """
        if self.setup['servicemode'] != 'disabled':
            for entry in services:
                entry.set("status", "off")
                self.InstallService(entry)

    def BundleUpdated(self, bundle, states):
        """The Bundle has been updated."""
        if self.setup['servicemode'] == 'disabled':
            return

        for entry in [ent for ent in bundle if self.handlesEntry(ent)]:
            restart = entry.get("restart", "true")
            if (restart.lower() == "false" or
                (restart.lower == "interactive" and
                 not self.setup['interactive'])):
                continue

            rv = None
            if entry.get('status') == 'on':
                if self.setup['servicemode'] == 'build':
                    rv = self.stop_service(entry)
                elif entry.get('name') not in self.restarted:
                    if self.setup['interactive']:
                        prompt = ('Restart service %s?: (y/N): ' %
                                  entry.get('name'))
                        ans = input(prompt)
                        if ans not in ['y', 'Y']:
                            continue
                    rv = self.restart_service(entry)
                    if not rv:
                        self.restarted.append(entry.get('name'))
            else:
                rv = self.stop_service(entry)
            if rv:
                self.logger.error("Failed to manipulate service %s" %
                                  (entry.get('name')))

    def Install(self, entries, states):
        """Install all entries in sublist."""
        install_entries = []
        for entry in entries:
            if entry.get('install', 'true').lower() == 'false':
                self.logger.info("Service %s installation is false. Skipping "
                                 "installation." % (entry.get('name')))
            else:
                install_entries.append(entry)
        return Tool.Install(self, install_entries, states)

    def InstallService(self, entry):
        """ Install a single service entry """
        raise NotImplementedError
