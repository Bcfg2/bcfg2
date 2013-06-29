""" Frame is the Client Framework that verifies and installs entries,
and generates statistics. """

import time
import fnmatch
import logging
import Bcfg2.Client.Tools
from Bcfg2.Client import prompt
from Bcfg2.Compat import any, all  # pylint: disable=W0622


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


# pylint: disable=W0702
# in frame we frequently want to catch all exceptions, regardless of
# type, so disable the pylint rule that catches that.


class Frame(object):
    """Frame is the container for all Tool objects and state information."""

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
        self.logger = logging.getLogger(__name__)
        for driver in drivers[:]:
            if (driver not in Bcfg2.Client.Tools.drivers and
                isinstance(driver, str)):
                self.logger.error("Tool driver %s is not available" % driver)
                drivers.remove(driver)

        tclass = {}
        for tool in drivers:
            if not isinstance(tool, str):
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

        for tool in list(tclass.values()):
            try:
                self.tools.append(tool(self.logger, setup, config))
            except Bcfg2.Client.Tools.ToolInstantiationError:
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
            self.logger.info("Loaded experimental tool drivers:")
            self.logger.info(experimental)

        # find entries not handled by any tools
        self.unhandled = [entry for struct in config
                          for entry in struct
                          if entry not in self.handled]

        if self.unhandled:
            self.logger.error("The following entries are not handled by any "
                              "tool:")
            for entry in self.unhandled:
                self.logger.error("%s:%s:%s" % (entry.tag, entry.get('type'),
                                                entry.get('name')))

        self.find_dups(config)

        pkgs = [(entry.get('name'), entry.get('origin'))
                for struct in config
                for entry in struct
                if entry.tag == 'Package']
        if pkgs:
            self.logger.debug("The following packages are specified in bcfg2:")
            self.logger.debug([pkg[0] for pkg in pkgs if pkg[1] is None])
            self.logger.debug("The following packages are prereqs added by "
                              "Packages:")
            self.logger.debug([pkg[0] for pkg in pkgs if pkg[1] == 'Packages'])

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
        if not self.setup['file']:
            if self.setup['decision'] == 'whitelist':
                dwl = self.setup['decision_list']
                w_to_rem = [e for e in self.whitelist
                            if not matches_white_list(e, dwl)]
                if w_to_rem:
                    self.logger.info("In whitelist mode: "
                                     "suppressing installation of:")
                    self.logger.info(["%s:%s" % (e.tag, e.get('name'))
                                      for e in w_to_rem])
                    self.whitelist = [x for x in self.whitelist
                                      if x not in w_to_rem]
            elif self.setup['decision'] == 'blacklist':
                b_to_rem = \
                    [e for e in self.whitelist
                     if not passes_black_list(e, self.setup['decision_list'])]
                if b_to_rem:
                    self.logger.info("In blacklist mode: "
                                     "suppressing installation of:")
                    self.logger.info(["%s:%s" % (e.tag, e.get('name'))
                                      for e in b_to_rem])
                    self.whitelist = [x for x in self.whitelist
                                      if x not in b_to_rem]

        # take care of important entries first
        if not self.dryrun:
            parent_map = dict((c, p)
                              for p in self.config.getiterator()
                              for c in p)
            for cfile in self.config.findall(".//Path"):
                if (cfile.get('name') not in self.__important__ or
                    cfile.get('type') != 'file' or
                    cfile not in self.whitelist):
                    continue
                parent = parent_map[cfile]
                if ((parent.tag == "Bundle" and
                     ((self.setup['bundle'] and
                       parent.get("name") not in self.setup['bundle']) or
                      (self.setup['skipbundle'] and
                       parent.get("name") in self.setup['skipbundle']))) or
                    (parent.tag == "Independent" and
                     (self.setup['bundle'] or self.setup['skipindep']))):
                    continue
                tools = [t for t in self.tools
                         if t.handlesEntry(cfile) and t.canVerify(cfile)]
                if tools:
                    if (self.setup['interactive'] and not
                        self.promptFilter("Install %s: %s? (y/N):", [cfile])):
                        self.whitelist.remove(cfile)
                        continue
                    try:
                        self.states[cfile] = tools[0].InstallPath(cfile)
                        if self.states[cfile]:
                            tools[0].modified.append(cfile)
                    except:
                        self.logger.error("Unexpected tool failure",
                                          exc_info=1)
                    cfile.set('qtext', '')
                    if tools[0].VerifyPath(cfile, []):
                        self.whitelist.remove(cfile)

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
                tool.Inventory(self.states)
            except:
                self.logger.error("%s.Inventory() call failed:" % tool.name,
                                  exc_info=1)

    def Decide(self):  # pylint: disable=R0912
        """Set self.whitelist based on user interaction."""
        iprompt = "Install %s: %s? (y/N): "
        rprompt = "Remove %s: %s? (y/N): "
        if self.setup['remove']:
            if self.setup['remove'] == 'all':
                self.removal = self.extra
            elif self.setup['remove'].lower() == 'services':
                self.removal = [entry for entry in self.extra
                                if entry.tag == 'Service']
            elif self.setup['remove'].lower() == 'packages':
                self.removal = [entry for entry in self.extra
                                if entry.tag == 'Package']
            elif self.setup['remove'].lower() == 'users':
                self.removal = [entry for entry in self.extra
                                if entry.tag in ['POSIXUser', 'POSIXGroup']]

        candidates = [entry for entry in self.states
                      if not self.states[entry]]

        if self.dryrun:
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
        if self.setup['bundle']:
            # warn if non-existent bundle given
            for bundle in self.setup['bundle']:
                if bundle not in all_bundle_names:
                    self.logger.info("Warning: Bundle %s not found" % bundle)
            bundles = [b for b in bundles
                       if b.get('name') in self.setup['bundle']]
        elif self.setup['indep']:
            bundles = [b for b in bundles if b.tag != 'Bundle']
        if self.setup['skipbundle']:
            # warn if non-existent bundle given
            if not self.setup['bundle_quick']:
                for bundle in self.setup['skipbundle']:
                    if bundle not in all_bundle_names:
                        self.logger.info("Warning: Bundle %s not found" %
                                         bundle)
            bundles = [b for b in bundles
                       if b.get('name') not in self.setup['skipbundle']]
        if self.setup['skipindep']:
            bundles = [b for b in bundles if b.tag == 'Bundle']

        self.whitelist = [e for e in self.whitelist
                          if any(e in b for b in bundles)]

        # first process prereq actions
        for bundle in bundles[:]:
            if bundle.tag != 'Bundle':
                continue
            bmodified = len([item for item in bundle
                             if item in self.whitelist])
            actions = [a for a in bundle.findall('./Action')
                       if (a.get('timing') != 'post' and
                           (bmodified or a.get('when') == 'always'))]
            # now we process all "always actions"
            if self.setup['interactive']:
                self.promptFilter(iprompt, actions)
            self.DispatchInstallCalls(actions)

            # need to test to fail entries in whitelist
            if False in [self.states[a] for a in actions]:
                # then display bundles forced off with entries
                self.logger.info("Bundle %s failed prerequisite action" %
                                 (bundle.get('name')))
                bundles.remove(bundle)
                b_to_remv = [ent for ent in self.whitelist if ent in bundle]
                if b_to_remv:
                    self.logger.info("Not installing entries from Bundle %s" %
                                     (bundle.get('name')))
                    self.logger.info(["%s:%s" % (e.tag, e.get('name'))
                                      for e in b_to_remv])
                    for ent in b_to_remv:
                        self.whitelist.remove(ent)

        self.logger.debug("Installing entries in the following bundle(s):")
        self.logger.debug("  %s" % ", ".join(b.get("name") for b in bundles
                                             if b.get("name")))

        if self.setup['interactive']:
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
                tool.Install(handled, self.states)
            except:
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
                    tool.Inventory(self.states, [bundle])
                except:
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
                if not self.setup['interactive']:
                    self.DispatchInstallCalls(clobbered)

        for bundle in self.config.findall('.//Bundle'):
            if (self.setup['bundle'] and
                bundle.get('name') not in self.setup['bundle']):
                # prune out unspecified bundles when running with -b
                continue
            if bundle in mbundles:
                self.logger.debug("Bundle %s was modified" %
                                  bundle.get('name'))
                func = "BundleUpdated"
            else:
                self.logger.debug("Bundle %s was not modified" %
                                  bundle.get('name'))
                func = "BundleNotUpdated"
            for tool in self.tools:
                try:
                    getattr(tool, func)(bundle, self.states)
                except:
                    self.logger.error("%s.%s() call failed:" %
                                      (tool.name, func), exc_info=1)

    def Remove(self):
        """Remove extra entries."""
        for tool in self.tools:
            extras = [entry for entry in self.removal
                      if tool.handlesEntry(entry)]
            if extras:
                try:
                    tool.Remove(extras)
                except:
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
        self.logger.info('Total managed entries:  %d' %
                         len(list(self.states.values())))
        self.logger.info('Unmanaged entries:      %d' % len(self.extra))
        if phase == 'final' and self.setup['extra']:
            for entry in sorted(self.extra, key=lambda e: e.tag + ":" +
                                e.get('name')):
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
        if not self.dryrun and self.setup['kevlar']:
            self.logger.info("Rechecking system inventory")
            self.Inventory()

    def Execute(self):
        """Run all methods."""
        self.Inventory()
        self.times['inventory'] = time.time()
        self.CondDisplayState('initial')
        self.InstallImportant()
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
        feedback = Bcfg2.Client.XML.Element("upload-statistics")
        stats = Bcfg2.Client.XML.SubElement(
            feedback,
            'Statistics',
            total=str(len(self.states)),
            version='2.0',
            revision=self.config.get('revision', '-1'))
        good_entries = [key for key, val in list(self.states.items()) if val]
        good = len(good_entries)
        stats.set('good', str(good))
        if any(not val for val in list(self.states.values())):
            stats.set('state', 'dirty')
        else:
            stats.set('state', 'clean')

        # List bad elements of the configuration
        for (data, ename) in [(self.modified, 'Modified'),
                              (self.extra, "Extra"),
                              (good_entries, "Good"),
                              ([entry for entry in self.states
                                if not self.states[entry]], "Bad")]:
            container = Bcfg2.Client.XML.SubElement(stats, ename)
            for item in data:
                item.set('qtext', '')
                container.append(item)
                item.text = None

        timeinfo = Bcfg2.Client.XML.Element("OpStamps")
        feedback.append(stats)
        for (event, timestamp) in list(self.times.items()):
            timeinfo.set(event, str(timestamp))
        stats.append(timeinfo)
        return feedback
