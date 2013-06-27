import os
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

    def check_missing_files(self):
        """ check that all files on the filesystem are known to Cfg """
        cfg = self.core.plugins['Cfg']

        # first, collect ignore patterns from handlers
        ignore = []
        for hdlr in cfg.handlers:
            ignore.extend(hdlr.__ignore__)

        # next, get a list of all non-ignored files on the filesystem
        all_files = set()
        for root, _, files in os.walk(cfg.data):
            all_files.update(os.path.join(root, fname)
                             for fname in files
                             if not any(fname.endswith("." + i)
                                        for i in ignore))

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
