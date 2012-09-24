"""All POSIX Type client support for Bcfg2."""

import os
import re
import sys
import shutil
from datetime import datetime
import Bcfg2.Client.Tools
from Bcfg2.Compat import walk_packages
from Bcfg2.Client.Tools.POSIX.base import POSIXTool


class POSIX(Bcfg2.Client.Tools.Tool):
    """POSIX File support code."""
    name = 'POSIX'

    def __init__(self, logger, setup, config):
        Bcfg2.Client.Tools.Tool.__init__(self, logger, setup, config)
        self.ppath = setup['ppath']
        self.max_copies = setup['max_copies']
        self._handlers = self._load_handlers()
        self.logger.debug("POSIX: Handlers loaded: %s" %
                          (", ".join(self._handlers.keys())))
        self.__req__ = dict(Path=dict())
        for etype, hdlr in self._handlers.items():
            self.__req__['Path'][etype] = hdlr.__req__
            self.__handles__.append(('Path', etype))
        # Tool.__init__() sets up the list of handled entries, but we
        # need to do it again after __handles__ has been populated. we
        # can't populate __handles__ when the class is created because
        # _load_handlers() _must_ be called at run-time, not at
        # compile-time.  This also has to _extend_ self.handled, not
        # set it, because self.handled has some really crazy
        # semi-global thing going that, frankly, scares the crap out
        # of me.
        for struct in config:
            self.handled.extend([e for e in struct
                                 if (e not in self.handled and
                                     self.handlesEntry(e))])

    def _load_handlers(self):
        """ load available POSIX tool handlers.  this must be called
        at run-time, not at compile-time, or we get wierd circular
        import issues. """
        rv = dict()
        for submodule in walk_packages(path=__path__, prefix=__name__ + "."):
            mname = submodule[1].rsplit('.', 1)[-1]
            if mname == 'base':
                continue
            module = getattr(__import__(submodule[1]).Client.Tools.POSIX,
                             mname)
            hdlr = getattr(module, "POSIX" + mname)
            if POSIXTool in hdlr.__mro__:
                # figure out what entry type this handler handles
                etype = hdlr.__name__[5:].lower()
                rv[etype] = hdlr(self.logger, self.setup, self.config)
        return rv

    def canVerify(self, entry):
        if not Bcfg2.Client.Tools.Tool.canVerify(self, entry):
            return False
        if not self._handlers[entry.get("type")].fully_specified(entry):
            self.logger.error('POSIX: Cannot verify incomplete entry %s. '
                              'Try running bcfg2-lint.' %
                              entry.get('name'))
            return False
        return True

    def canInstall(self, entry):
        """Check if entry is complete for installation."""
        if not Bcfg2.Client.Tools.Tool.canInstall(self, entry):
            return False
        if not self._handlers[entry.get("type")].fully_specified(entry):
            self.logger.error('POSIX: Cannot install incomplete entry %s. '
                              'Try running bcfg2-lint.' %
                              entry.get('name'))
            return False
        return True

    def InstallPath(self, entry):
        """Dispatch install to the proper method according to type"""
        self.logger.debug("POSIX: Installing entry %s:%s:%s" %
                          (entry.tag, entry.get("type"), entry.get("name")))
        self._paranoid_backup(entry)
        return self._handlers[entry.get("type")].install(entry)

    def VerifyPath(self, entry, modlist):
        """Dispatch verify to the proper method according to type"""
        self.logger.debug("POSIX: Verifying entry %s:%s:%s" %
                          (entry.tag, entry.get("type"), entry.get("name")))
        ret = self._handlers[entry.get("type")].verify(entry, modlist)
        if self.setup['interactive'] and not ret:
            entry.set('qtext',
                      '%s\nInstall %s %s: (y/N) ' %
                      (entry.get('qtext', ''),
                       entry.get('type'), entry.get('name')))
        return ret

    def _prune_old_backups(self, entry):
        """ Remove old paranoid backup files """
        bkupnam = entry.get('name').replace('/', '_')
        bkup_re = re.compile(
            bkupnam + r'_\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{6}$')
        # current list of backups for this file
        try:
            bkuplist = [f for f in os.listdir(self.ppath) if
                        bkup_re.match(f)]
        except OSError:
            err = sys.exc_info()[1]
            self.logger.error("POSIX: Failed to create backup list in %s: %s" %
                              (self.ppath, err))
            return
        bkuplist.sort()
        while len(bkuplist) >= int(self.max_copies):
            # remove the oldest backup available
            oldest = bkuplist.pop(0)
            self.logger.info("POSIX: Removing old backup %s" % oldest)
            try:
                os.remove(os.path.join(self.ppath, oldest))
            except OSError:
                err = sys.exc_info()[1]
                self.logger.error("POSIX: Failed to remove old backup %s: %s" %
                                  (os.path.join(self.ppath, oldest), err))

    def _paranoid_backup(self, entry):
        """ Take a backup of the specified entry for paranoid mode """
        if (entry.get("paranoid", 'false').lower() == 'true' and
            self.setup.get("paranoid", False) and
            entry.get('current_exists', 'true') == 'true' and
            not os.path.isdir(entry.get("name"))):
            self._prune_old_backups(entry)
            bkupnam = "%s_%s" % (entry.get('name').replace('/', '_'),
                                 datetime.isoformat(datetime.now()))
            bfile = os.path.join(self.ppath, bkupnam)
            try:
                shutil.copy(entry.get('name'), bfile)
                self.logger.info("POSIX: Backup of %s saved to %s" %
                                 (entry.get('name'), bfile))
            except IOError:
                err = sys.exc_info()[1]
                self.logger.error("POSIX: Failed to create backup file for "
                                  "%s: %s" % (entry.get('name'), err))
