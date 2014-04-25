""" Cfg creator that creates SSL keys """

from Bcfg2.Utils import Executor
from Bcfg2.Server.Plugins.Cfg import CfgCreationError, XMLCfgCreator


class CfgSSLCAKeyCreator(XMLCfgCreator):
    """ Cfg creator that creates SSL keys """

    #: Different configurations for different clients/groups can be
    #: handled with Client and Group tags within sslkey.xml
    __specific__ = False

    __basenames__ = ["sslkey.xml"]

    cfg_section = "sslca"

    def create_data(self, entry, metadata):
        self.logger.info("Cfg: Generating new SSL key for %s" % self.name)
        spec = self.XMLMatch(metadata)
        key = spec.find("Key")
        if not key:
            key = dict()
        ktype = key.get('type', 'rsa')
        bits = key.get('bits', '2048')
        if ktype == 'rsa':
            cmd = ["openssl", "genrsa", bits]
        elif ktype == 'dsa':
            cmd = ["openssl", "dsaparam", "-noout", "-genkey", bits]
        result = Executor().run(cmd)
        if not result.success:
            raise CfgCreationError("Failed to generate key %s for %s: %s" %
                                   (self.name, metadata.hostname,
                                    result.error))
        self.write_data(result.stdout, **self.get_specificity(metadata))
        return result.stdout
