""" ``bcfg2-lint`` plugin for :ref:`Cfg
<server-plugins-generators-cfg>` """


import os
import Bcfg2.Options
from fnmatch import fnmatch
from Bcfg2.Server.Lint import ServerPlugin


class Cfg(ServerPlugin):
    """ warn about Cfg issues """

    def Run(self):
        for basename, entry in list(self.core.plugins['Cfg'].entries.items()):
            self.check_pubkey(basename, entry)
        self.check_missing_files()

    @classmethod
    def Errors(cls):
        return {"no-pubkey-xml": "warning",
                "unknown-cfg-files": "error",
                "extra-cfg-files": "error"}

    def check_pubkey(self, basename, entry):
        """ check that privkey.xml files have corresponding pubkey.xml
        files """
        if "privkey.xml" not in entry.entries:
            return
        privkey = entry.entries["privkey.xml"]
        if not self.HandlesFile(privkey.name):
            return

        pubkey = basename + ".pub"
        if pubkey not in self.core.plugins['Cfg'].entries:
            self.LintError("no-pubkey-xml",
                           "%s has no corresponding pubkey.xml at %s" %
                           (basename, pubkey))
        else:
            pubset = self.core.plugins['Cfg'].entries[pubkey]
            if "pubkey.xml" not in pubset.entries:
                self.LintError("no-pubkey-xml",
                               "%s has no corresponding pubkey.xml at %s" %
                               (basename, pubkey))

    def _list_path_components(self, path):
        """ Get a list of all components of a path.  E.g.,
        ``self._list_path_components("/foo/bar/foobaz")`` would return
        ``["foo", "bar", "foo", "baz"]``.  The list is not guaranteed
        to be in order."""
        rv = []
        remaining, component = os.path.split(path)
        while component != '':
            rv.append(component)
            remaining, component = os.path.split(remaining)
        return rv

    def check_missing_files(self):
        """ check that all files on the filesystem are known to Cfg """
        cfg = self.core.plugins['Cfg']

        # first, collect ignore patterns from handlers
        ignore = set()
        for hdlr in Bcfg2.Options.setup.cfg_handlers:
            ignore.update(hdlr.__ignore__)

        # next, get a list of all non-ignored files on the filesystem
        all_files = set()
        for root, _, files in os.walk(cfg.data):
            for fname in files:
                fpath = os.path.join(root, fname)
                # check against the handler ignore patterns and the
                # global FAM ignore list
                if (not any(fname.endswith("." + i) for i in ignore) and
                    not any(fnmatch(fpath, p)
                            for p in Bcfg2.Options.setup.ignore_files) and
                    not any(fnmatch(c, p)
                            for p in Bcfg2.Options.setup.ignore_files
                            for c in self._list_path_components(fpath))):
                    all_files.add(fpath)

        # next, get a list of all files known to Cfg
        cfg_files = set()
        for root, eset in cfg.entries.items():
            cfg_files.update(os.path.join(cfg.data, root.lstrip("/"), fname)
                             for fname in eset.entries.keys())

        # finally, compare the two
        unknown_files = all_files - cfg_files
        extra_files = cfg_files - all_files
        if unknown_files:
            self.LintError(
                "unknown-cfg-files",
                "Files on the filesystem could not be understood by Cfg: %s" %
                "; ".join(unknown_files))
        if extra_files:
            self.LintError(
                "extra-cfg-files",
                "Cfg has entries for files that do not exist on the "
                "filesystem: %s\nThis is probably a bug." %
                "; ".join(extra_files))
