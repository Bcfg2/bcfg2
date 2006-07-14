'''This is the basic toolset class for the Bcfg2 client'''
__revision__ = '$Revision$'

from stat import S_ISVTX, S_ISGID, S_ISUID, S_IXUSR, S_IWUSR, S_IRUSR, S_IXGRP
from stat import S_IWGRP, S_IRGRP, S_IXOTH, S_IWOTH, S_IROTH, ST_MODE, S_ISDIR
from stat import S_IFREG, ST_UID, ST_GID, S_ISREG, S_IFDIR, S_ISLNK

import binascii, copy, difflib, grp, logging, lxml.etree, os, popen2, pwd, stat, sys, xml.sax.saxutils

def calcPerms(initial, perms):
    '''This compares ondisk permissions with specified ones'''
    pdisp = [{1:S_ISVTX, 2:S_ISGID, 4:S_ISUID}, {1:S_IXUSR, 2:S_IWUSR, 4:S_IRUSR},
             {1:S_IXGRP, 2:S_IWGRP, 4:S_IRGRP}, {1:S_IXOTH, 2:S_IWOTH, 4:S_IROTH}]
    tempperms = initial
    if len(perms) == 3:
        perms = '0%s' % (perms)
    pdigits = [int(perms[digit]) for digit in range(4)]
    for index in range(4):
        for (num, perm) in pdisp[index].iteritems():
            if pdigits[index] & num:
                tempperms |= perm
    return tempperms

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

class Toolset(object):
    '''The toolset class contains underlying command support and all states'''
    __important__ = []
    __name__ = 'Toolset'
    pkgtool = {'echo': ('%s', ['name'])}
    
    def __init__(self, cfg, setup):
        '''Install initial configs, and setup state structures'''
        object.__init__(self)
        self.setup = setup
        self.cfg = cfg
        self.states = {}
        self.structures = {}
        self.modified = []
        self.installed = {}
        self.logger = logging.getLogger('Toolset')
        self.pkgwork = {'add':[], 'update':[], 'remove':[]}
        self.extra_services = []
        if self.__important__:
            for cfile in [cfl for cfl in cfg.findall(".//ConfigFile") if cfl.get('name') in self.__important__]:
                self.VerifyEntry(cfile)
                if not self.states[cfile]:
                    self.InstallConfigFile(cfile)
        self.statistics = lxml.etree.Element("Statistics")

    def saferun(self, command):
        '''Run a command in a pipe dealing with stdout buffer overloads'''
        self.logger.debug('> %s' % command)

        runpipe = readonlypipe(command, bufsize=16384)
        output = ''
        cmdstat = -1
        while cmdstat == -1:
            runpipe.fromchild.flush()
            moreOutput = runpipe.fromchild.read()
            if len(moreOutput) > 0:                
                self.logger.debug('< %s' % moreOutput)
            output += moreOutput
            cmdstat = runpipe.poll()

        return (cmdstat, [line for line in output.split('\n') if line])

    def CondDisplayState(self, phase):
        '''Conditionally print tracing information'''
        self.logger.info('\nPhase: %s' % phase)
        self.logger.info('Correct entries:\t%d' % self.states.values().count(True))
        self.logger.info('Incorrect entries:\t%d' % self.states.values().count(False))
        self.logger.info('Total managed entries:\t%d' % len(self.states.values()))
        if not self.setup['bundle']:
            self.logger.info('Unmanaged entries:\t%d' % len(self.pkgwork['remove']))

        if ((self.states.values().count(False) == 0) and not self.pkgwork['remove']):
            self.logger.info('All entries correct.')
            
    # These next functions form the external API

    def Refresh(self):
        '''Update based on current pkg system state'''
        return

    def Inventory(self):
        '''Inventory system status'''
        self.logger.info("Inventorying system...")
        self.Inventory_Entries()
        all = copy.deepcopy(self.installed)
        desired = {}
        for entry in self.cfg.findall(".//Package"):
            desired[entry.attrib['name']] = entry
        self.pkgwork = {'update':[], 'add':[], 'remove':[]}
        for pkg, entry in desired.iteritems():
            if self.states.get(entry, True):
                # package entry verifies
                del all[pkg]
            else:
                if all.has_key(pkg):
                    # wrong version
                    del all[pkg]
                    self.pkgwork['update'].append(entry)
                else:
                    # new pkg
                    self.pkgwork['add'].append(entry)

        # pkgwork contains all one-way verification data now
        # all data remaining in all is extra packages
        self.pkgwork['remove'] = all.keys()

    def Inventory_Entries(self):
        '''Build up workqueue for installation'''
        # build initial set of states
        unexamined = [(child, []) for child in self.cfg.getchildren()]
        while unexamined:
            (entry, modlist) = unexamined.pop()
            if entry.tag not in ['Bundle', 'Independant']:
                self.VerifyEntry(entry, modlist)
            else:
                modlist = [cfile.get('name') for cfile in entry.getchildren() if cfile.tag == 'ConfigFile']
                unexamined += [(child, modlist) for child in entry.getchildren()]
                self.structures[entry] = False

        for structure in self.cfg.getchildren():
            self.CheckStructure(structure)

    def CheckStructure(self, structure):
        '''Check structures with bundle verification semantics'''
        if structure in self.modified:
            self.modified.remove(structure)
            if structure.tag == 'Bundle':
                # check for clobbered data
                modlist = [cfile.get('name') for cfile in structure.getchildren() if cfile.tag == 'ConfigFile']
                for entry in structure.getchildren():
                    self.VerifyEntry(entry, modlist)
        try:
            state = [self.states[entry] for entry in structure.getchildren()]
            if False not in state:
                self.structures[structure] = True
        except KeyError, msg:
            print "State verify evidently failed for %s" % (msg)
            self.structures[structure] = False

    def GenerateStats(self, clientVersion):
        '''Generate XML summary of execution statistics'''
        stats = self.statistics

        # Calculate number of total bundles and structures
        total =  len(self.states)
        stats.set('total', str(total))
        # Calculate number of good bundles and structures
        good = len([key for key, val in self.states.iteritems() if val])
        stats.set('good', str(good))
        stats.set('version', '2.0')
        stats.set('client_version', clientVersion)
        stats.set('revision', self.cfg.get('revision', '-1'))

        if len([key for key, val in self.states.iteritems() if not val]) == 0:
            stats.set('state', 'clean')
            dirty = 0
        else:
            stats.set('state', 'dirty')
            dirty = 1
        #stats.set('time', asctime(localtime()))

        # List bad elements of the configuration
        flows = [(dirty, "Bad"), (self.modified, "Modified")]
        for (condition, tagName) in flows:
            if condition:
                container = lxml.etree.SubElement(stats, tagName)
                for ent in [key for key, val in self.states.iteritems() if not val]:
                    newent = lxml.etree.SubElement(container, ent.tag, name=ent.get('name', 'None'))
                    for field in [item for item in 'current_exists', 'current_diff' if item in ent.attrib]:
                        newent.set(field, ent.get(field))
                        del ent.attrib[field]
                    failures = [key for key in ent.attrib if key[:8] == 'current_']
                    for fail in failures:
                        for field in [fail, fail[8:]]:
                            try:
                                newent.set(field, ent.get(field))
                            except:
                                self.logger.error("Failed to set field %s for entry %s, value %s" %
                                                  (field, ent.get('name'), ent.get(field)))
                    if 'severity' in ent.attrib:
                        newent.set('severity', ent.get('severity'))
        if self.extra_services + self.pkgwork['remove']:
            extra = lxml.etree.SubElement(stats, "Extra")
            [lxml.etree.SubElement(extra, "Service", name=svc, current_status='on')
             for svc in self.extra_services]
            [lxml.etree.SubElement(extra, "Package", name=pkg,
                                   current_version=self.installed[pkg]) for pkg in self.pkgwork['remove']]
        return stats

    # the next two are dispatch functions

    def VerifyEntry(self, entry, modlist = []):
        '''Dispatch call to Verify<tagname> and save state in self.states'''
        try:
            method = getattr(self, "Verify%s" % (entry.tag))
            # verify state and stash value in state
            if entry.tag == 'Package':
                self.states[entry] = method(entry, modlist)
            else:
                self.states[entry] = method(entry)
        except:
            self.logger.error("Failure in VerifyEntry", exc_info=1)
            self.logger.error("Entry: %s" % (lxml.etree.tostring(entry)))

    def InstallEntry(self, entry):
        '''Dispatch call to self.Install<tagname>'''
        try:
            method = getattr(self, "Install%s"%(entry.tag))
            self.states[entry] = method(entry)
        except:
            self.logger.error("Failure in InstallEntry", exc_info=1)

    # All remaining operations implement the mechanics of POSIX cfg elements

    def VerifySymLink(self, entry):
        '''Verify SymLink Entry'''
        try:
            sloc = os.readlink(entry.get('name'))
            if sloc == entry.get('to'):
                return True
            self.logger.debug("Symlink %s points to %s, should be %s" % (entry.get('name'),
                                                                         sloc, entry.get('to')))
            entry.set('current_to', sloc)
            return False
        except OSError:
            entry.set('current_exists', 'false')
            return False

    def InstallSymLink(self, entry):
        '''Install SymLink Entry'''
        self.logger.info("Installing Symlink %s" % (entry.get('name')))
        try:
            fmode = os.lstat(entry.get('name'))[ST_MODE]
            if S_ISREG(fmode) or S_ISLNK(fmode):
                self.logger.debug("Non-directory entry already exists at %s" % (entry.get('name')))
                os.unlink(entry.get('name'))
            elif S_ISDIR(fmode):
                self.logger.debug("Directory entry already exists at %s" % (entry.get('name')))
                self.saferun("mv %s/ %s.bak" % (entry.get('name'), entry.get('name')))
            else:
                os.unlink(entry.get('name'))
        except OSError:
            self.logger.info("Symlink %s cleanup failed" % (entry.get('name')))
        try:
            os.symlink(entry.get('to'), entry.get('name'))
            return True
        except OSError:
            return False

    def VerifyDirectory(self, entry):
        '''Verify Directory Entry'''
        while len(entry.get('perms', '')) < 4:
            entry.set('perms', '0' + entry.get('perms', ''))
        try:
            ondisk = os.stat(entry.get('name'))
        except OSError:
            entry.set('current_exists', 'false')
            self.logger.debug("%s %s does not exist" %
                              (entry.tag, entry.get('name')))
            return False
        try:
            owner = pwd.getpwuid(ondisk[ST_UID])[0]
            group = grp.getgrgid(ondisk[ST_GID])[0]
        except (OSError, KeyError):
            self.logger.error('User resolution failing')
            owner = 'root'
            group = 'root'
        perms = oct(os.stat(entry.get('name'))[ST_MODE])[-4:]
        if ((owner == entry.get('owner')) and
            (group == entry.get('group')) and
            (perms == entry.get('perms'))):
            return True
        else:
            if owner != entry.get('owner'):
                entry.set('current_owner', owner)
                self.logger.debug("%s %s ownership wrong" % (entry.tag, entry.get('name')))
            if group != entry.get('group'):
                entry.set('current_group', group)
                self.logger.debug("%s %s group wrong" % (entry.tag, entry.get('name')))
            if perms != entry.get('perms'):
                entry.set('current_perms', perms)
                self.logger.debug("%s %s permissions wrong: are %s should be %s" %
                               (entry.tag, entry.get('name'), perms, entry.get('perms')))
            return False

    def InstallDirectory(self, entry):
        '''Install Directory Entry'''
        self.logger.info("Installing Directory %s" % (entry.get('name')))
        try:
            fmode = os.lstat(entry.get('name'))
            if not S_ISDIR(fmode[ST_MODE]):
                self.logger.debug("Found a non-directory entry at %s" % (entry.get('name')))
                try:
                    os.unlink(entry.get('name'))
                except OSError:
                    self.logger.info("Failed to unlink %s" % (entry.get('name')))
                    return False
            else:
                self.logger.debug("Found a pre-existing directory at %s" % (entry.get('name')))
                exists = True
        except OSError:
            # stat failed
            exists = False

        if not exists:
            parent = "/".join(entry.get('name').split('/')[:-1])
            if parent:
                try:
                    os.lstat(parent)
                except:
                    self.logger.debug('Creating parent path for directory %s' % (entry.get('name')))
                    for idx in xrange(len(parent.split('/')[:-1])):
                        current = '/'+'/'.join(parent.split('/')[1:2+idx])
                        try:
                            sloc = os.lstat(current)
                            try:
                                if not S_ISDIR(sloc[ST_MODE]):
                                    os.unlink(current)
                                    os.mkdir(current)
                            except OSError:
                                return False
                        except OSError:
                            try:
                                os.mkdir(current)
                            except OSError:
                                return False

            try:
                os.mkdir(entry.get('name'))
            except OSError:
                self.logger.error('Failed to create directory %s' % (entry.get('name')))
                return False
        try:
            os.chown(entry.get('name'),
                  pwd.getpwnam(entry.get('owner'))[2], grp.getgrnam(entry.get('group'))[2])
            os.chmod(entry.get('name'), calcPerms(S_IFDIR, entry.get('perms')))
            return True
        except (OSError, KeyError):
            self.logger.error('Permission fixup failed for %s' % (entry.get('name')))
            return False

    def VerifyConfigFile(self, entry):
        '''Install ConfigFile Entry'''
        # configfile verify is permissions check + content check
        permissionStatus = self.VerifyDirectory(entry)
        if entry.get('encoding', 'ascii') == 'base64':
            tempdata = binascii.a2b_base64(entry.text)
        elif entry.get('empty', 'false') == 'true':
            tempdata = ''
        else:
            tempdata = entry.text

        try:
            content = open(entry.get('name')).read()
        except IOError:
            # file does not exist
            return False
        contentStatus = content == tempdata
        if not contentStatus:
            diff = '\n'.join([x for x in difflib.unified_diff(content.split('\n'), tempdata.split('\n'))])
            try:
                entry.set("current_diff", xml.sax.saxutils.quoteattr(diff))
            except:
                pass
        return contentStatus and permissionStatus

    def InstallConfigFile(self, entry):
        '''Install ConfigFile Entry'''
        if entry.text == None and entry.get('empty', 'false') != 'true':
            self.logger.error(
                "Incomplete information for ConfigFile %s. Cannot install" % (entry.get('name')))
            return False
        self.logger.info("Installing ConfigFile %s" % (entry.get('name')))

        if self.setup['dryrun']:
            return False
        parent = "/".join(entry.get('name').split('/')[:-1])
        if parent:
            try:
                os.lstat(parent)
            except:
                self.logger.debug('Creating parent path for config file %s' % (entry.get('name')))
                for idx in xrange(len(parent.split('/')[:-1])):
                    current = '/'+'/'.join(parent.split('/')[1:2+idx])
                    try:
                        sloc = os.lstat(current)
                        try:
                            if not S_ISDIR(sloc[ST_MODE]):
                                os.unlink(current)
                                os.mkdir(current)
                        except OSError:
                            return False
                    except OSError:
                        try:
                            os.mkdir(current)
                        except OSError:
                            return False

        # If we get here, then the parent directory should exist
        try:
            newfile = open("%s.new"%(entry.get('name')), 'w')
            if entry.get('encoding', 'ascii') == 'base64':
                filedata = binascii.a2b_base64(entry.text)
            elif entry.get('empty', 'false') == 'true':
                filedata = ''
            else:
                filedata = entry.text
            newfile.write(filedata)
            newfile.close()
            try:
                os.chown(newfile.name, pwd.getpwnam(entry.get('owner'))[2],
                         grp.getgrnam(entry.get('group'))[2])
            except KeyError:
                os.chown(newfile.name, 0, 0)
            os.chmod(newfile.name, calcPerms(S_IFREG, entry.get('perms')))
            if entry.get("paranoid", False) and self.setup.get("paranoid", False):
                self.saferun("cp %s /var/cache/bcfg2/%s" % (entry.get('name')))
            os.rename(newfile.name, entry.get('name'))
            return True
        except (OSError, IOError), err:
            if err.errno == 13:
                self.logger.info("Failed to open %s for writing" % (entry.get('name')))
            else:
                print err
            return False

    def VerifyPackage(self, _, dummy):
        '''Dummy package verification method. Cannot succeed'''
        return False

    def VerifyPermissions(self, entry):
        '''Verify method for abstract permission'''
        try:
            sinfo = os.stat(entry.get('name'))
        except OSError:
            self.logger.debug("Entry %s doesn't exist" % entry.get('name'))
            entry.set('current_exists', 'false')
            return False
        # pad out perms if needed
        while len(entry.get('perms', '')) < 4:
            entry.set('perms', '0' + entry.get('perms', ''))
        perms = oct(sinfo[ST_MODE])[-4:]
        if perms == entry.get('perms'):
            return True
        self.logger.debug("Entry %s permissions incorrect" % entry.get('name'))
        entry.set('current_perms', perms)
        return False
    
    def InstallPermissions(self, entry):
        '''Install method for abstract permission'''
        try:
            sinfo = os.stat(entry.get('name'))
        except OSError:
            self.logger.debug("Entry %s doesn't exist" % entry.get('name'))
            return False
        for ftype in ['DIR', 'REG', 'CHR', 'BLK']:
            if getattr(stat, "S_IS%s" % ftype)(sinfo[ST_MODE]):
                os.chmod(entry.get('name'), calcPerms(getattr(stat, "S_IF%s" % ftype), entry.get('perms')))
                return True
        self.logger.info("Entry %s has unknown file type" % entry.get('name'))
        return False

    def VerifyPostInstall(self, _):
        '''Postinstall verification method'''
        return True

    def HandleBundleDeps(self):
        '''Handle bundles depending on what has been modified'''
        for entry in [child for child in self.structures if child.tag == 'Bundle']:
            bchildren = entry.getchildren()
            if [b_ent for b_ent in bchildren if b_ent in self.modified]:
                # This bundle has been modified
                self.logger.info("%s %s needs update" % (entry.tag, entry.get('name', '???')))
                modfiles = [cfile.get('name') for cfile in bchildren if cfile.tag == 'ConfigFile']
                for child in bchildren:
                    if child.tag == 'Package':
                        self.VerifyPackage(child, modfiles)
                    else:
                        self.VerifyEntry(child)
                        if not self.states.has_key(child):
                            self.logger.error("Could not get state for entry %s: %s" % (child.tag, child.get('name')))
                            continue
                        if not self.states[child]:
                            self.logger.debug("Reinstalling clobbered entry %s %s" % (child.tag,
                                                                                      child.get('name')))
                            self.InstallEntry(child)
                            self.VerifyEntry(child)
                    self.logger.debug("Re-checked entry %s %s: %s" %
                                      (child.tag, child.get('name'), self.states[child]))
                for postinst in [entry for entry in bchildren if entry.tag == 'PostInstall']:
                    self.saferun(postinst.get('name'))
                for svc in [svc for svc in bchildren if svc.tag == 'Service' and
                            svc.get('status', 'off') == 'on']:
                    if self.setup['build']:
                        # stop services in miniroot
                        self.saferun('/etc/init.d/%s stop' % svc.get('name'))
                    else:
                        self.logger.debug('Restarting service %s' % svc.get('name'))
                        self.saferun('/etc/init.d/%s %s' % (svc.get('name'), svc.get('reload', 'reload')))
            
        for entry in self.structures:
            if [strent for strent in entry.getchildren() if not self.states.get(strent, False)]:
                self.logger.info("%s %s incomplete" % (entry.tag, entry.get('name', "")))
            else:
                self.structures[entry] = True

    def HandleExtra(self):
        '''deal with extra configuration during installation'''
        return False

    def displayWork(self):
        '''Display all entries that will be upgraded'''
        if self.pkgwork['update']:
            self.logger.info("Packages to update:")
            self.logger.info([pkg.get('name') for pkg in self.pkgwork['update']])
        if self.pkgwork['add']:
            self.logger.info("Packages to add:")
            self.logger.info([pkg.get('name') for pkg in self.pkgwork['add']])
        if self.pkgwork['remove']:
            self.logger.info("Packages to remove:")
            self.logger.info(self.pkgwork['remove'])
        if [entry for entry in self.states if not (self.states[entry] or entry.tag == 'Package')]:
            self.logger.info("Entries to update:")
            self.logger.info(["%s: %s" % (entry.tag, entry.get('name'))
                              for entry in self.states if not (self.states[entry]
                                                               or entry.tag == 'Package')])
        if self.extra_services:
            self.logger.info("Services to remove:")
            self.logger.info(self.extra_services)

    def Install(self):
        '''Correct detected misconfigurations'''
        if self.setup['dryrun']:
            self.logger.info("Dry-run mode: no changes will be made")
        else:
            self.logger.info("Updating the system")
        self.logger.info("")
        self.HandleExtra()

        if self.setup['dryrun'] or self.setup['debug']:
            self.displayWork()
        if self.setup['dryrun']:
            return
        
        # use quick package ops from here on
        self.setup['quick'] = True

        # build up work queue
        work = self.pkgwork['add'] + self.pkgwork['update']
        # add non-package entries
        work += [ent for ent in self.states if ent.tag != 'Package' and not self.states[ent]]

        # Counters
        ## Packages left to install
        left = len(work) + len(self.pkgwork['remove'])
        ## Packages installed in previous iteration
        old = left + 1
        ## loop iterations performed
        count = 1

        # Installation loop
        while ((0 < left < old) and (count < 20)):
            # Print pass info
            self.logger.info("Starting pass %s" % (count))
            self.logger.info("%s Entries left" % (len(work)))
            if self.setup['bundle']:
                self.logger.info("%s new, %s update" % (len(self.pkgwork['add']), len(self.pkgwork['update'])))
            else:
                self.logger.info("%s new, %s update, %s remove" %
                                 (len(self.pkgwork['add']), len(self.pkgwork['update']),
                                  len(self.pkgwork['remove'])))

            # Update counters
            count = count + 1
            old = left

            self.logger.info("Installing non-package entries")
            [self.InstallEntry(ent) for ent in work if ent.tag != 'Package']

            packages = [pkg for pkg in work if pkg.tag == 'Package']
            ptypes = []
            for pkg in packages:
                if pkg.get('type') not in ptypes:
                    ptypes.append(pkg.get('type'))
            if packages:
                for pkgtype in ptypes:
                    # try single large install
                    self.logger.info("Trying single pass package install for pkgtype %s" % pkgtype)
                    if not self.pkgtool.has_key(pkgtype):
                        self.logger.info("No support for pkgtype %s" % (pkgtype))
                        continue
                    pkgtool = self.pkgtool[pkgtype]
                    pkglist = [pkg for pkg in packages if pkg.get('type') == pkgtype]
                    for field in pkgtool[1][1]:
                        pkglist = [pkg for pkg in pkglist if pkg.attrib.has_key(field)]
                    if not pkglist:
                        self.logger.debug("No complete/installable packages of type %s" % pkgtype)
                        continue
                    pkgargs = " ".join([pkgtool[1][0] % tuple([pkg.get(field) for field in pkgtool[1][1]])
                                        for pkg in pkglist])

                    self.logger.debug("Installing packages: :%s:" % pkgargs)
                    self.logger.debug("Running command ::%s::" % (pkgtool[0] % pkgargs))
                    cmdrc = self.saferun(pkgtool[0] % pkgargs)[0]

                    if cmdrc == 0:
                        self.logger.info("Single Pass Succeded")
                        # set all package states to true and flush workqueues
                        pkgnames = [pkg.get('name') for pkg in pkglist]
                        for entry in [entry for entry in self.states.keys()
                                      if entry.tag == 'Package' and entry.get('type') == pkgtype
                                      and entry.get('name') in pkgnames]:
                            self.logger.debug('Setting state to true for pkg %s' % (entry.get('name')))
                            self.states[entry] = True
                            [self.pkgwork[listname].remove(entry) for listname in ['add', 'update']
                             if self.pkgwork[listname].count(entry)]
                        self.Refresh()
                    else:
                        self.logger.error("Single Pass Failed")
                        # do single pass installs
                        self.Refresh()
                        for pkg in pkglist:
                            # handle state tracking updates
                            if self.VerifyPackage(pkg, []):
                                self.logger.info("Forcing state to true for pkg %s" % (pkg.get('name')))
                                self.states[pkg] = True
                            else:
                                self.logger.info("Installing pkg %s version %s" %
                                                 (pkg.get('name'), pkg.get('version')))
                                cmdrc = self.saferun(pkgtool[0] %
                                                     (pkgtool[1][0] %
                                                      tuple([pkg.get(field) for field in pkgtool[1][1]])))
                                if cmdrc[0] == 0:
                                    self.states[pkg] = True
                                else:
                                    self.logger.error("Failed to install package %s" % (pkg.get('name')))
            for entry in [ent for ent in work if self.states[ent]]:
                work.remove(entry)
                self.modified.append(entry)
            left = len(work) + len(self.pkgwork['remove'])
        self.HandleBundleDeps()
