'''Frame is the Client Framework that verifies and installs entries, and generates statistics'''
__revision__ = '$Revision$'

import logging, time
import Bcfg2.Client.Tools

def promptFilter(prompt, entries):
    '''Filter a supplied list based on user input'''
    ret = []
    for entry in [entry for entry in entries]:
        try:
            if raw_input(prompt % (entry.tag, entry.get('name'))) in ['y', 'Y']:
                ret.append(entry)
        except:
            continue
    return ret

toolset_defs = {'rh': {'Service':'chkconfig', 'Package':'rpm'},
                'debian': {'Service':'deb', 'Package':'deb'}}

class Frame:
    '''Frame is the container for all Tool objects and state information'''
    def __init__(self, config, setup, times):
        self.config = config
        self.times = times
        self.times['initialization'] = time.time()
        self.setup = setup
        self.tools = []
        self.states = {}
        self.whitelist = []
        self.removal = []
        self.logger = logging.getLogger("Bcfg2.Client.Frame")
        if self.setup['drivers']:
            tools = self.setup['drivers'].split(',')
        else:
            tools = Bcfg2.Client.Tools.__all__[:]
        for tool in tools:
            try:
                tool_class = "Bcfg2.Client.Tools.%s" % tool
                mod = __import__(tool_class, globals(), locals(), ['*'])
            except ImportError:
                continue

            try:
                self.tools.append(getattr(mod, tool)(self.logger, setup, config, self.states))
            except Bcfg2.Client.Tools.toolInstantiationError:
                continue
            except:
                self.logger.error("Failed to instantiate tool %s" % (tool), exc_info=1)
        self.logger.info("Loaded tool drivers:")
        self.logger.info([tool.__name__ for tool in self.tools])
        if not self.setup['dryrun']:
            for cfile in [cfl for cfl in config.findall(".//ConfigFile") \
                          if cfl.get('name') in self.__important__]:
                tool = [t for t in self.tools if t.handlesEntry(cfile)][0]
                self.states[cfile] = tool.VerifyConfigFile(cfile, [])
                if not self.states[cfile]:
                    tool.InstallConfigFile(cfile)
        # find entries not handled by any tools
        problems = [entry for struct in config for entry in struct if entry not in self.handled]
        if toolset_defs.has_key(config.get('toolset')):
            tdefs = toolset_defs[config.get('toolset')]
            for problem in problems[:]:
                if tdefs.has_key(problem.tag):
                    problem.set('type', tdefs[problem.tag])
                    problems.remove(problem)

        if problems:
            self.logger.error("The following entries are not handled by any tool:")
            self.logger.error(["%s:%s:%s" % (entry.tag, entry.get('type'), \
                                             entry.get('name')) for entry in problems])
            self.logger.error("")
                    
    def __getattr__(self, name):
        if name in ['extra', 'handled', 'modified', '__important__']:
            ret = []
            for tool in self.tools:
                ret += getattr(tool, name)
            return ret
        elif self.__dict__.has_key(name):
            return self.__dict__[name]
        raise AttributeError, name

    def Inventory(self):
        '''Verify all entries, find extra entries, and build up workqueues'''
        # initialize all states
        for struct in self.config.getchildren():
            for entry in struct.getchildren():
                self.states[entry] = False
        for tool in self.tools:
            try:
                tool.Inventory()
            except:
                self.logger.error("%s.Inventory() call failed:" % tool.__name__, exc_info=1)

    def Decide(self):
        '''Set self.whitelist based on user interaction'''
        prompt = "Would you like to install %s: %s? (y/N): "
        rprompt = "Would you like to remove %s: %s? (y/N): "
        if self.setup['remove']:
            if self.setup['remove'] == 'all':
                self.removal = self.extra
            elif self.setup['remove'] == 'services':
                self.removal = [entry for entry in self.extra if entry.tag == 'Service']
            elif self.setup['remove'] == 'packages':
                self.removal = [entry for entry in self.extra if entry.tag == 'Package']

        if self.setup['dryrun']:
            updated = [entry for entry in self.states if not self.states[entry]]
            if updated:
                self.logger.info("In dryrun mode: suppressing entry installation for:")
                self.logger.info(["%s:%s" % (entry.tag, entry.get('name')) for entry \
                                  in updated])
            if self.removal:
                self.logger.info("In dryrun mode: suppressing entry removal for:")
                self.logger.info(["%s:%s" % (entry.tag, entry.get('name')) for entry \
                                  in self.removal])
            self.removal = []
            return
        elif self.setup['interactive']:
            self.whitelist = promptFilter(prompt, [entry for entry in self.states \
                                                   if not self.states[entry]])
            self.removal = promptFilter(rprompt, self.removal)
        elif self.setup['bundle']:
            # only install entries in specified bundle
            mbs = [bund for bund in self.config.findall('./Bundle') \
                   if bund.get('name') == self.setup['bundle']]
            if not mbs:
                self.logger.error("Could not find bundle %s" % (self.setup['bundle']))
                return
            self.whitelist = [entry for entry in self.states if not self.states[entry] \
                              and entry in mbs[0].getchildren()]
        else:
            # all systems are go
            self.whitelist = [entry for entry in self.states if not self.states[entry]]

    def DispatchInstallCalls(self, entries):
        '''Dispatch install calls to underlying tools'''
        for tool in self.tools:
            handled = [entry for entry in entries if tool.canInstall(entry)]
            if not handled:
                continue
            try:
                tool.Install(handled)
            except:
                self.logger.error("%s.Install() call failed:" % tool.__name__, exc_info=1)

    def Install(self):
        '''Install all entries'''
        self.DispatchInstallCalls(self.whitelist)
        if self.modified:
            # Handle Bundle interdeps
            mods = self.modified
            mbundles = [struct for struct in self.config if struct.tag == 'Bundle' and \
                        [mod for mod in mods if mod in struct]]
            if mbundles:
                self.logger.info("The Following Bundles have been modifed:")
                self.logger.info([mbun.get('name') for mbun in mbundles])
                self.logger.info("")
            tbm = [(t, b) for t in self.tools for b in mbundles]
            for tool, bundle in tbm:
                try:
                    tool.Inventory(bundle)
                except:
                    self.logger.error("%s.Inventory() call failed:" % tool.__name__, exc_info=1)
            clobbered = [entry for bundle in mbundles for entry in bundle \
                         if not self.states[entry]]
            if not self.setup['interactive']:
                self.DispatchInstallCalls(clobbered)
            for tool, bundle in tbm:
                try:
                    tool.BundleUpdated(bundle)
                except:
                    self.logger.error("%s.BundleUpdated() call failed:" % (tool.__name__), exc_info=1)
                
    def Remove(self):
        '''Remove extra entries'''
        for tool in self.tools:
            extras = [entry for entry in self.removal if tool.handlesEntry(entry)]
            if extras:
                try:
                    tool.Remove(extras)
                except:
                    self.logger.error("%s.Remove() failed" % tool.__name__, exc_info=1)

    def CondDisplayState(self, phase):
        '''Conditionally print tracing information'''
        self.logger.info('\nPhase: %s' % phase)
        self.logger.info('Correct entries:\t%d' % self.states.values().count(True))
        self.logger.info('Incorrect entries:\t%d' % self.states.values().count(False))
        self.logger.info('Total managed entries:\t%d' % len(self.states.values()))
        self.logger.info('Unmanaged entries:\t%d' % len(self.extra))
        self.logger.info("")

        if ((self.states.values().count(False) == 0) and not self.extra):
            self.logger.info('All entries correct.')

    def ReInventory(self):
        '''Recheck everything'''
        if not self.setup['dryrun'] and self.setup['kevlar']:
            self.logger.info("Rechecking system inventory")
            self.Inventory()

    def Execute(self):
        '''Run all methods'''
        self.Inventory()
        self.times['inventory'] = time.time()
        self.CondDisplayState('initial')
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
        '''Generate XML summary of execution statistics'''
        feedback = Bcfg2.Client.XML.Element("upload-statistics")
        stats = Bcfg2.Client.XML.SubElement(feedback, \
                                            'Statistics', total=str(len(self.states)),
                                            client_version=__revision__, version='2.0',
                                            revision=self.config.get('revision', '-1'))
        good = len([key for key, val in self.states.iteritems() if val])
        stats.set('good', str(good))
        if len([key for key, val in self.states.iteritems() if not val]) == 0:
            stats.set('state', 'clean')
        else:
            stats.set('state', 'dirty')

        # List bad elements of the configuration
        for (data, ename) in [(self.modified, 'Modified'), (self.extra, "Extra"), \
                              ([entry for entry in self.states if not \
                                self.states[entry]], "Bad")]:
            container = Bcfg2.Client.XML.SubElement(stats, ename)
            [container.append(item) for item in data]

        timeinfo = Bcfg2.Client.XML.Element("OpStamps")
        feedback.append(stats)
        for (event, timestamp) in self.times.iteritems():
            timeinfo.set(event, str(timestamp))
        stats.append(timeinfo)
        return feedback
