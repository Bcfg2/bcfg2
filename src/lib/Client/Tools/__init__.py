'''This contains all Bcfg2 Tool modules'''
__revision__ = '$Revision$'

__all__ = ["APT", "Blast", "Chkconfig", "DebInit", "Encap", "Portage",
           "PostInstall", "POSIX", "RPM", "RcUpdate", "SMF", "SYSV"]

import os, popen2, stat, sys, Bcfg2.Client.XML

class toolInstantiationError(Exception):
    '''This error is called if the toolset cannot be instantiated'''
    pass

class readonlypipe(popen2.Popen4):
    '''This pipe sets up stdin --> /dev/null'''
    def __init__(self, cmd, bufsize=-1):
        popen2._cleanup()
        c2pread, c2pwrite = os.pipe()
        null = open('/dev/null', 'w+')
        self.pid = os.fork()
        if self.pid == 0:
            # Child
            os.dup2(null.fileno(), sys.__stdin__.fileno())
            #os.dup2(p2cread, 0)
            os.dup2(c2pwrite, 1)
            os.dup2(c2pwrite, 2)
            self._run_child(cmd)
        os.close(c2pwrite)
        self.fromchild = os.fdopen(c2pread, 'r', bufsize)
        popen2._active.append(self)

class executor:
    '''this class runs stuff for us'''
    def __init__(self, logger):
        self.logger = logger
        
    def run(self, command):
        '''Run a command in a pipe dealing with stdout buffer overloads'''
        self.logger.debug('> %s' % command)

        runpipe = readonlypipe(command, bufsize=16384)
        output = ''
        cmdstat = -1
        while cmdstat == -1:
            runpipe.fromchild.flush()
            moreOutput = runpipe.fromchild.readline()
            if len(moreOutput) > 0:                
                self.logger.debug('< %s' % moreOutput[:-1])
            output += moreOutput
            cmdstat = runpipe.poll()
        for line in runpipe.fromchild.readlines():
            if len(line) > 0:
                self.logger.debug('< %s' % line[:-1])
            output += line

        return (cmdstat, [line for line in output.split('\n') if line])

class Tool:
    '''All tools subclass this. It defines all interfaces that need to be defined'''
    __name__ = 'Tool'
    __execs__ = []
    __handles__ = []
    __req__ = {}
    __important__ = []
    
    def __init__(self, logger, setup, config, states):
        self.setup = setup
        self.logger = logger
        if not hasattr(self, '__ireq__'):
            self.__ireq__ = self.__req__
        self.config = config
        self.cmd = executor(logger)
        self.states = states
        self.modified = []
        self.extra = []
        self.handled = [entry for struct in self.config for entry in struct \
                        if self.handlesEntry(entry)]
        for filename in self.__execs__:
            try:
                mode = stat.S_IMODE(os.stat(filename)[stat.ST_MODE])
                if mode & stat.S_IEXEC != stat.S_IEXEC:
                    self.logger.debug("%s: %s not executable" % \
                                      (self.__name__, filename))
                    raise toolInstantiationError
            except OSError:
                raise toolInstantiationError
            except:
                self.logger.debug("%s failed" % filename, exc_info=1)
                raise toolInstantiationError

    def BundleUpdated(self, _):
        '''This callback is used when bundle updates occur'''
        pass

    def Inventory(self, structures=[]):
        '''Dispatch verify calls to underlying methods'''
        if not structures:
            structures = self.config.getchildren()
        for (struct, entry) in [(struct, entry) for struct in structures \
                                for entry in struct.getchildren() \
                                if self.canVerify(entry)]:
            try:
                func = getattr(self, "Verify%s" % (entry.tag))
                self.states[entry] = func(entry, self.buildModlist(entry, struct))
            except:
                self.logger.error(
                    "Unexpected failure of verification method for entry type %s" \
                    % (entry.tag), exc_info=1)
        self.extra = self.FindExtra()

    def Install(self, entries):
        '''Install all entries in sublist'''
        for entry in entries:
            try:
                func = getattr(self, "Install%s" % (entry.tag))
                self.states[entry] = func(entry)
                self.modified.append(entry)
            except:
                self.logger.error("Unexpected failure of install method for entry type %s" \
                                  % (entry.tag), exc_info=1)

    def Remove(self, entries):
        '''Remove specified extra entries'''
        pass

    def getSupportedEntries(self):
        '''return a list of supported entries'''
        return [entry for struct in self.config.getchildren() for entry in struct.getchildren() \
                if self.handlesEntry(entry)]
    
    def handlesEntry(self, entry):
        '''return if entry is handled by this Tool'''
        return (entry.tag, entry.get('type')) in self.__handles__

    def buildModlist(self, entry, struct):
        '''Build a list of potentially modified POSIX paths for this entry'''
        if entry.tag != 'Package' or struct.tag != 'Bundle':
            return []
        return [sentry.get('name') for sentry in struct if sentry.tag in \
                ['ConfigFile', 'SymLink', 'Directory']]

    def canVerify(self, entry):
        '''test if entry has enough information to be verified'''
        if not self.handlesEntry(entry):
            return False
        
        if [attr for attr in self.__req__[entry.tag] if attr not in entry.attrib]:
            self.logger.error("Incomplete information for entry %s:%s; cannot verify" \
                              % (entry.tag, entry.get('name')))
            return False
        return True


    def FindExtra(self):
        '''Return a list of extra entries'''
        return []

    def canInstall(self, entry):
        '''test if entry has enough information to be installed'''
        if not self.handlesEntry(entry):
            return False
        if [attr for attr in self.__ireq__[entry.tag] if attr not in entry.attrib]:
            self.logger.error("Incomplete information for entry %s:%s; cannot install" \
                              % (entry.tag, entry.get('name')))
            return False
        return True
    
class PkgTool(Tool):
    '''PkgTool provides a one-pass install with fallback for use with packaging systems'''
    pkgtool = ('echo %s', ('%s', ['name']))
    pkgtype = 'echo'
    __name__ = 'PkgTool'

    def __init__(self, logger, setup, config, states):
        Tool.__init__(self, logger, setup, config, states)
        self.installed = {}
        self.Remove = self.RemovePackages
        self.FindExtra = self.FindExtraPackages
        self.RefreshPackages()

    def VerifyPackage(self, dummy, _):
        '''Dummy verification method'''
        return False
    
    def Install(self, packages):
        '''Run a one-pass install, followed by single pkg installs in case of failure'''
        self.logger.info("Trying single pass package install for pkgtype %s" % \
                         self.pkgtype)

        data = [tuple([pkg.get(field) for field in self.pkgtool[1][1]]) for pkg in packages]
        pkgargs = " ".join([self.pkgtool[1][0] % datum for datum in data])

        self.logger.debug("Installing packages: :%s:" % pkgargs)
        self.logger.debug("Running command ::%s::" % (self.pkgtool[0] % pkgargs))

        cmdrc = self.cmd.run(self.pkgtool[0] % pkgargs)[0]
        if cmdrc == 0:
            self.logger.info("Single Pass Succeded")
            # set all package states to true and flush workqueues
            pkgnames = [pkg.get('name') for pkg in packages]
            for entry in [entry for entry in self.states.keys()
                          if entry.tag == 'Package' and entry.get('type') == self.pkgtype
                          and entry.get('name') in pkgnames]:
                self.logger.debug('Setting state to true for pkg %s' % (entry.get('name')))
                self.states[entry] = True
            self.RefreshPackages()
        else:
            self.logger.error("Single Pass Failed")
            # do single pass installs
            self.RefreshPackages()
            for pkg in packages:
                # handle state tracking updates
                if self.VerifyPackage(pkg, []):
                    self.logger.info("Forcing state to true for pkg %s" % (pkg.get('name')))
                    self.states[pkg] = True
                else:
                    self.logger.info("Installing pkg %s version %s" %
                                     (pkg.get('name'), pkg.get('version')))
                    cmdrc = self.cmd.run(self.pkgtool[0] %
                                         (self.pkgtool[1][0] %
                                          tuple([pkg.get(field) for field in self.pkgtool[1][1]])))
                    if cmdrc[0] == 0:
                        self.states[pkg] = True
                    else:
                        self.logger.error("Failed to install package %s" % (pkg.get('name')))
        for entry in [ent for ent in packages if self.states[ent]]:
            self.modified.append(entry)

    def RefreshPackages(self):
        '''Dummy state refresh method'''
        pass

    def RemovePackages(self, packages):
        '''Dummy implementation of package removal method'''
        pass

    def FindExtraPackages(self):
        '''Find extra packages'''
        packages = [entry.get('name') for entry in self.getSupportedEntries()]
        extras = [key for key in self.installed if key not in packages]
        return [Bcfg2.Client.XML.Element('Package', name=name, type=self.pkgtype) \
                for name in extras]

class SvcTool(Tool):
    '''This class defines basic Service behavior'''
    __name__ = 'SvcTool'

    def BundleUpdated(self, bundle):
        '''The Bundle has been updated'''
        for entry in bundle:
            if self.handlesEntry(entry):
                if entry.get('status') == 'on':
                    self.logger.debug('Restarting service %s' % entry.get('name'))
                    self.cmd.run('/etc/init.d/%s %s' % \
                                 (entry.get('name'), entry.get('reload', 'reload')))
                else:
                    self.logger.debug('Stopping service %s' % entry.get('name'))
                    self.cmd.run('/etc/init.d/%s stop' %  (entry.get('name')))
