""" The CfgAuthorizedKeysGenerator generates ``authorized_keys`` files
based on an XML specification of which SSH keypairs should granted
access. """

import lxml.etree
from Bcfg2.Server.Plugin import StructFile, PluginExecutionError
from Bcfg2.Server.Plugins.Cfg import CfgGenerator, SETUP, CFG
from Bcfg2.Server.Plugins.Metadata import ClientMetadata


class CfgAuthorizedKeysGenerator(CfgGenerator, StructFile):
    """ The CfgAuthorizedKeysGenerator generates authorized_keys files
    based on an XML specification of which SSH keypairs should granted
    access. """

    #: Different configurations for different clients/groups can be
    #: handled with Client and Group tags within authorizedkeys.xml
    __specific__ = False

    #: Handle authorized keys XML files
    __basenames__ = ['authorizedkeys.xml', 'authorized_keys.xml']

    #: This handler is experimental, in part because it depends upon
    #: the (experimental) CfgPrivateKeyCreator handler
    experimental = True

    def __init__(self, fname):
        CfgGenerator.__init__(self, fname, None, None)
        StructFile.__init__(self, fname)
        self.cache = dict()
        self.core = CFG.core
    __init__.__doc__ = CfgGenerator.__init__.__doc__

    @property
    def category(self):
        """ The name of the metadata category that generated keys are
        specific to """
        if (SETUP.cfp.has_section("sshkeys") and
            SETUP.cfp.has_option("sshkeys", "category")):
            return SETUP.cfp.get("sshkeys", "category")
        return None

    def handle_event(self, event):
        CfgGenerator.handle_event(self, event)
        StructFile.HandleEvent(self, event)
        self.cache = dict()
    handle_event.__doc__ = CfgGenerator.handle_event.__doc__

    def get_data(self, entry, metadata):
        spec = self.XMLMatch(metadata)
        rv = []
        for allow in spec.findall("Allow"):
            params = ''
            if allow.find("Params") is not None:
                params = ",".join("=".join(p)
                                  for p in allow.find("Params").attrib.items())

            pubkey_name = allow.get("from")
            if pubkey_name:
                host = allow.get("host")
                group = allow.get("group")
                if host:
                    key_md = self.core.build_metadata(host)
                elif group:
                    key_md = ClientMetadata("dummy", group, [group], [],
                                            set(), set(), dict(), None,
                                            None, None, None)
                elif (self.category and
                      not metadata.group_in_category(self.category)):
                    self.logger.warning("Cfg: %s ignoring Allow from %s: "
                                        "No group in category %s" %
                                        (metadata.hostname, pubkey_name,
                                         self.category))
                    continue
                else:
                    key_md = metadata

                key_entry = lxml.etree.Element("Path", name=pubkey_name)
                try:
                    self.core.Bind(key_entry, key_md)
                except PluginExecutionError:
                    self.logger.info("Cfg: %s skipping Allow from %s: "
                                     "No key found" % (metadata.hostname,
                                                       pubkey_name))
                    continue
                if not key_entry.text:
                    self.logger.warning("Cfg: %s skipping Allow from %s: "
                                        "Empty public key" %
                                        (metadata.hostname, pubkey_name))
                    continue
                pubkey = key_entry.text
            elif allow.text:
                pubkey = allow.text.strip()
            else:
                self.logger.warning("Cfg: %s ignoring empty Allow tag: %s" %
                                    (metadata.hostname,
                                     lxml.etree.tostring(allow)))
                continue
            rv.append(" ".join([params, pubkey]).strip())
        return "\n".join(rv)
    get_data.__doc__ = CfgGenerator.get_data.__doc__
