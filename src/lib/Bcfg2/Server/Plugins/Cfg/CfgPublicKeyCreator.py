""" The CfgPublicKeyCreator invokes
:class:`Bcfg2.Server.Plugins.Cfg.CfgPrivateKeyCreator.CfgPrivateKeyCreator`
to create SSH keys on the fly. """

import os
import sys
import tempfile
import lxml.etree
from Bcfg2.Utils import Executor
from Bcfg2.Server.Plugin import StructFile, PluginExecutionError
from Bcfg2.Server.Plugins.Cfg import CfgCreator, CfgCreationError, CFG


class CfgPublicKeyCreator(CfgCreator, StructFile):
    """ .. currentmodule:: Bcfg2.Server.Plugins.Cfg

    The CfgPublicKeyCreator creates SSH public keys on the fly. It is
    invoked by :class:`CfgPrivateKeyCreator.CfgPrivateKeyCreator` to
    handle the creation of the public key, and can also call
    :class:`CfgPrivateKeyCreator.CfgPrivateKeyCreator` to trigger the
    creation of a keypair when a public key is created. """

    #: Different configurations for different clients/groups can be
    #: handled with Client and Group tags within privkey.xml
    __specific__ = False

    #: Handle XML specifications of private keys
    __basenames__ = ['pubkey.xml']

    def __init__(self, fname):
        CfgCreator.__init__(self, fname)
        StructFile.__init__(self, fname)
        self.cfg = CFG
        self.core = CFG.core
        self.cmd = Executor()

    def create_data(self, entry, metadata):
        if entry.get("name").endswith(".pub"):
            privkey = entry.get("name")[:-4]
        else:
            raise CfgCreationError("Cfg: Could not determine private key for "
                                   "%s: Filename does not end in .pub" %
                                   entry.get("name"))

        privkey_entry = lxml.etree.Element("Path", name=privkey)
        try:
            self.core.Bind(privkey_entry, metadata)
        except PluginExecutionError:
            raise CfgCreationError("Cfg: Could not bind %s (private key for "
                                   "%s): %s" % (privkey, self.name,
                                                sys.exc_info()[1]))

        try:
            eset = self.cfg.entries[privkey]
            creator = eset.best_matching(metadata,
                                         eset.get_handlers(metadata,
                                                           CfgCreator))
        except KeyError:
            raise CfgCreationError("Cfg: No private key defined for %s (%s)" %
                                   (self.name, privkey))
        except PluginExecutionError:
            raise CfgCreationError("Cfg: No privkey.xml defined for %s "
                                   "(private key for %s)" % (privkey,
                                                             self.name))

        specificity = creator.get_specificity(metadata)
        fname = self.get_filename(**specificity)

        # if the private key didn't exist, then creating it may have
        # created the private key, too.  check for it first.
        if os.path.exists(fname):
            return open(fname).read()
        else:
            # generate public key from private key
            fd, privfile = tempfile.mkstemp()
            try:
                os.fdopen(fd, 'w').write(privkey_entry.text)
                cmd = ["ssh-keygen", "-y", "-f", privfile]
                self.debug_log("Cfg: Extracting SSH public key from %s: %s" %
                               (privkey, " ".join(cmd)))
                result = self.cmd.run(cmd)
                if not result.success:
                    raise CfgCreationError("Cfg: Failed to extract public key "
                                           "from %s: %s" % (privkey,
                                                            result.error))
                self.write_data(result.stdout, **specificity)
                return result.stdout
            finally:
                os.unlink(privfile)

    def handle_event(self, event):
        CfgCreator.handle_event(self, event)
        StructFile.HandleEvent(self, event)
    handle_event.__doc__ = CfgCreator.handle_event.__doc__
