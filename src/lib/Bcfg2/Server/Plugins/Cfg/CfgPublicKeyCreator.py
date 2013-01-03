""" The CfgPublicKeyCreator invokes
:class:`Bcfg2.Server.Plugins.Cfg.CfgPrivateKeyCreator.CfgPrivateKeyCreator`
to create SSH keys on the fly. """

import lxml.etree
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
    __init__.__doc__ = CfgCreator.__init__.__doc__

    def create_data(self, entry, metadata):
        if entry.get("name").endswith(".pub"):
            privkey = entry.get("name")[:-4]
        else:
            raise CfgCreationError("Cfg: Could not determine private key for "
                                   "%s: Filename does not end in .pub" %
                                   entry.get("name"))

        if privkey not in self.cfg.entries:
            raise CfgCreationError("Cfg: Could not find Cfg entry for %s "
                                   "(private key for %s)" % (privkey,
                                                             self.name))
        eset = self.cfg.entries[privkey]
        try:
            creator = eset.best_matching(metadata,
                                         eset.get_handlers(metadata,
                                                           CfgCreator))
        except PluginExecutionError:
            raise CfgCreationError("Cfg: No privkey.xml defined for %s "
                                   "(private key for %s)" % (privkey,
                                                             self.name))

        privkey_entry = lxml.etree.Element("Path", name=privkey)
        pubkey = creator.create_data(privkey_entry, metadata,
                                     return_pair=True)[0]
        return pubkey
    create_data.__doc__ = CfgCreator.create_data.__doc__

    def handle_event(self, event):
        CfgCreator.handle_event(self, event)
        StructFile.HandleEvent(self, event)
    handle_event.__doc__ = CfgCreator.handle_event.__doc__
