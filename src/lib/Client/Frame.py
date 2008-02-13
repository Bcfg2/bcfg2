'''Frame is the Client Framework that verifies and installs entries, and generates statistics'''
__revision__ = '$Revision$'

import logging, time, types
import Bcfg2.Client.Tools

def cmpent(ent1, ent2):
    '''Sort entries'''
    if ent1.tag != ent2.tag:
        return cmp(ent1.tag, ent2.tag)
    else:
        return cmp(ent1.get('name'), ent2.get('name'))

def promptFilter(prompt, entries):
    '''Filter a supplied list based on user input'''
    ret = []
    entries.sort(cmpent)
    for entry in entries[:]:
        if 'qtext' in entry.attrib:
            iprompt = entry.get('qtext')
        else:
            iprompt = prompt % (entry.tag, entry.get('name'))
        try:
            if raw_input(iprompt) in ['y', 'Y']:
                ret.append(entry)
        except:
            continue
    return ret

class Frame:
    '''Frame is the container for all Tool objects and state information'''
    def __init__(self, config, setup, times, drivers, dryrun):
        self.config = config
        self.times = times
        self.dryrun = dryrun
        self.times['initialization'] = time.time()
        self.setup = setup
        self.tools = []
        self.states = {}
        self.whitelist = []
        self.blacklist = []
        self.removal = []
        self.logger = logging.getLogger("Bcfg2.Client.Frame")
        for driver in drivers[:]:
            if driver not in Bcfg2.Client.Tools.drivers and \
                   isinstance(driver, types.StringType):
                self.logger.error("Tool driver %s is not available" % driver)
                drivers.remove(driver)
                
        tclass = {}
        for tool in drivers:
            if not isinstance(tool, types.StringType):
                tclass[time.time()] = tool
            tool_class = "Bcfg2.Client.Tools.%s" % tool
            try:
                tclass[tool] = getattr(__import__(tool_class, globals(),
                                                  locals(), ['*']),
                                       tool)
            except ImportError:
                continue
            except:
                self.logger.error("Tool %s unexpectedly failed to load" % tool,
                                  exc_info=1)

        for tool in tclass.values():
            try:
                self.tools.append(tool(self.logger, setup, config, self.states))
            except Bcfg2.Client.Tools.toolInstantiationError:
                continue
            except:
                self.logger.error("Failed to instantiate tool %s" % (tool), exc_info=1)

        for tool in self.tools[:]:
            for conflict in getattr(tool, 'conflicts', []):
                [self.tools.remove(item) for item in self.tools \
                 if item.__name__ == conflict]

        self.logger.info("Loaded tool drivers:")
        self.logger.info([tool.__name__ for tool in self.tools])
        if not self.dryrun:
            for cfile in [cfl for cfl in config.findall(".//ConfigFile") \
                          if cfl.get('name') in self.__important__]:
                tl= [t for t in self.tools if t.handlesEntry(cfile) \
                     and t.canVerify(cfile)]
                if tl:
                    if not tl[0].VerifyConfigFile(cfile, []):
                        try:
                            self.states[cfile] = tl[0].InstallConfigFile(cfile)
                        except:
                            self.logger.error("Unexpected tool failure",
                                              exc_info=1)
        # find entries not handled by any tools
        problems = [entry for struct in config for entry in struct if entry not in self.handled]

        if problems:
            self.logger.error("The following entries are not handled by any tool:")
            self.logger.error(["%s:%s:%s" % (entry.tag, entry.get('type'), \
                                             entry.get('name')) for entry in problems])
            self.logger.error("")
        entries = [(entry.tag, entry.get('name')) for struct in config for entry in struct]
        multi = []
        for entry in entries[:]:
            if entries.count(entry) > 1:
                multi.append(entry)
                entries.remove(entry)
        if multi:
            self.logger.debug("The following entries are included multiple times:")
            self.logger.debug(["%s:%s" % entry for entry in multi])
            
                    
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
        prompt = "Install %s: %s? (y/N): "
        rprompt = "Remove %s: %s? (y/N): "
        if self.setup['remove']:
            if self.setup['remove'] == 'all':
                self.removal = self.extra
            elif self.setup['remove'] == 'services':
                self.removal = [entry for entry in self.extra if entry.tag == 'Service']
            elif self.setup['remove'] == 'packages':
                self.removal = [entry for entry in self.extra if entry.tag == 'Package']

        candidates = [entry for entry in self.states if not self.states[entry]]
        self.whitelist = [entry for entry in self.states if not self.states[entry]]
        if self.dryrun:
            if self.whitelist:
                self.logger.info("In dryrun mode: suppressing entry installation for:")
                self.logger.info(["%s:%s" % (entry.tag, entry.get('name')) for entry \
                                  in self.whitelist])
                self.whitelist = []
            if self.removal:
                self.logger.info("In dryrun mode: suppressing entry removal for:")
                self.logger.info(["%s:%s" % (entry.tag, entry.get('name')) for entry \
                                  in self.removal])
            self.removal = []
            return
        # Here is where most of the work goes
        # first perform bundle filtering
        if self.setup['bundle']:
            bundles = [b for b in self.config.findall('./Bundle') \
                       if b.get('name') in self.setup['bundle']]
            self.whitelist = [e for e in self.whitelist if \
                              True in [e in b for b in bundles]]
        else:
            bundles = self.config.getchildren()

        # first process prereq actions
        for bundle in bundles[:]:
            if bundle.tag != 'Bundle':
                continue
            actions = [a for a in bundle.findall('./Action') \
                       if a.get('timing') != 'post']
            # now we process all "always actions"
            bmodified = len([item for item in bundle if item in self.whitelist])
            for action in actions:
                if bmodified or action.get('when') == 'always':
                    self.DispatchInstallCalls([action])
            # need to test to fail entries in whitelist
            if False in [self.states[a] for a in actions]:
                # then display bundles forced off with entries
                self.logger.info("Bundle %s failed prerequisite action" % \
                                 (bundle.get('name')))
                bundles.remove(bundle)
                b_to_remv = [ent for ent in self.whitelist if ent in bundle]
                if b_to_remv:
                    self.logger.info("Not installing entries from Bundle %s" % \
                                     (bundle.get('name')))
                    self.logger.info(["%s:%s" % (e.tag, e.get('name')) for e in b_to_remv])
                    [self.whitelist.remove(ent) for ent in b_to_remv]

        if self.setup['interactive']:
            self.whitelist = promptFilter(prompt, self.whitelist) 
            self.removal = promptFilter(rprompt, self.removal) 

        for entry in candidates:
            if entry not in self.whitelist:
                self.blacklist.append(entry)

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
        mods = self.modified
        mbundles = [struct for struct in self.config.findall('Bundle') if \
                    [mod for mod in mods if mod in struct]]

        if self.modified:
            # Handle Bundle interdeps
            if mbundles:
                self.logger.info("The Following Bundles have been modified:")
                self.logger.info([mbun.get('name') for mbun in mbundles])
                self.logger.info("")
            tbm = [(t, b) for t in self.tools for b in mbundles]
            for tool, bundle in tbm:
                try:
                    tool.Inventory([bundle])
                except:
                    self.logger.error("%s.Inventory() call failed:" % tool.__name__, exc_info=1)
            clobbered = [entry for bundle in mbundles for entry in bundle \
                         if not self.states[entry] and entry not in self.blacklist]
            if clobbered:
                self.logger.debug("Found clobbered entries:")
                self.logger.debug(["%s:%s" % (entry.tag, entry.get('name')) \
                                   for entry in clobbered])
                if not self.setup['interactive']:
                    self.DispatchInstallCalls(clobbered)

        for bundle in self.config.findall('.//Bundle'):
            for tool in self.tools:
                try:
                    if bundle in mbundles:
                        tool.BundleUpdated(bundle)
                    else:
                        tool.BundleNotUpdated(bundle)
                except:
                    self.logger.error("%s.BundleNotUpdated() call failed:" % \
                                      (tool.__name__), exc_info=1)
                
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
        if phase == 'final' and self.states.values().count(False):
            self.logger.info(["%s:%s" % (entry.tag, entry.get('name')) for \
                              entry in self.states if not self.states[entry]])
        self.logger.info('Total managed entries:\t%d' % len(self.states.values()))
        self.logger.info('Unmanaged entries:\t%d' % len(self.extra))
        if phase == 'final' and self.setup['extra']:
            self.logger.info(["%s:%s" % (entry.tag, entry.get('name')) \
                              for entry in self.extra])
                
        self.logger.info("")

        if ((self.states.values().count(False) == 0) and not self.extra):
            self.logger.info('All entries correct.')

    def ReInventory(self):
        '''Recheck everything'''
        if not self.dryrun and self.setup['kevlar']:
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
            for item in data:
                item.set('qtext', '')
                container.append(item)
                item.text = None

        timeinfo = Bcfg2.Client.XML.Element("OpStamps")
        feedback.append(stats)
        for (event, timestamp) in self.times.iteritems():
            timeinfo.set(event, str(timestamp))
        stats.append(timeinfo)
        return feedback
