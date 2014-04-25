""" Check for data that claims to be encrypted, but is not. """

import os
import lxml.etree
import Bcfg2.Options
from Bcfg2.Server.Lint import ServerlessPlugin
from Bcfg2.Server.Encryption import is_encrypted


class Crypto(ServerlessPlugin):
    """ Check for templated scripts or executables. """

    def Run(self):
        if os.path.exists(os.path.join(Bcfg2.Options.setup.repository, "Cfg")):
            self.check_cfg()
        if os.path.exists(os.path.join(Bcfg2.Options.setup.repository,
                                       "Properties")):
            self.check_properties()
        # TODO: check all XML files

    @classmethod
    def Errors(cls):
        return {"unencrypted-cfg": "error",
                "empty-encrypted-properties": "error",
                "unencrypted-properties": "error"}

    def check_cfg(self):
        """ Check for Cfg files that end in .crypt but aren't encrypted """
        for root, _, files in os.walk(
                os.path.join(Bcfg2.Options.setup.repository, "Cfg")):
            for fname in files:
                fpath = os.path.join(root, fname)
                if self.HandlesFile(fpath) and fname.endswith(".crypt"):
                    if not is_encrypted(open(fpath).read()):
                        self.LintError(
                            "unencrypted-cfg",
                            "%s is a .crypt file, but it is not encrypted" %
                            fpath)

    def check_properties(self):
        """ Check for Properties data that has an ``encrypted`` attribute but
        aren't encrypted """
        for root, _, files in os.walk(
                os.path.join(Bcfg2.Options.setup.repository, "Properties")):
            for fname in files:
                fpath = os.path.join(root, fname)
                if self.HandlesFile(fpath) and fname.endswith(".xml"):
                    xdata = lxml.etree.parse(fpath)
                    for elt in xdata.xpath('//*[@encrypted]'):
                        if not elt.text:
                            self.LintError(
                                "empty-encrypted-properties",
                                "Element in %s has an 'encrypted' attribute, "
                                "but no text content: %s" %
                                (fpath, self.RenderXML(elt)))
                        elif not is_encrypted(elt.text):
                            self.LintError(
                                "unencrypted-properties",
                                "Element in %s has an 'encrypted' attribute, "
                                "but is not encrypted: %s" %
                                (fpath, self.RenderXML(elt)))
