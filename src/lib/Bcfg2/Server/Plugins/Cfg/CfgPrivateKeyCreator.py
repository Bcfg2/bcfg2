""" The CfgPrivateKeyCreator creates SSH keys on the fly. """

import os
import shutil
import tempfile
import Bcfg2.Options
from Bcfg2.Utils import Executor
from Bcfg2.Server.Plugins.Cfg import XMLCfgCreator, CfgCreationError
from Bcfg2.Server.Plugins.Cfg.CfgPublicKeyCreator import CfgPublicKeyCreator


class CfgPrivateKeyCreator(XMLCfgCreator):
    """The CfgPrivateKeyCreator creates SSH keys on the fly. """

    #: Different configurations for different clients/groups can be
    #: handled with Client and Group tags within privkey.xml
    __specific__ = False

    #: Handle XML specifications of private keys
    __basenames__ = ['privkey.xml']

    cfg_section = "sshkeys"
    options = [
        Bcfg2.Options.Option(
            cf=("sshkeys", "category"), dest="sshkeys_category",
            help="Metadata category that generated SSH keys are specific to"),
        Bcfg2.Options.Option(
            cf=("sshkeys", "passphrase"), dest="sshkeys_passphrase",
            help="Passphrase used to encrypt generated SSH private keys")]

    def __init__(self, fname):
        XMLCfgCreator.__init__(self, fname)
        pubkey_path = os.path.dirname(self.name) + ".pub"
        pubkey_name = os.path.join(pubkey_path, os.path.basename(pubkey_path))
        self.pubkey_creator = CfgPublicKeyCreator(pubkey_name)
        self.cmd = Executor()

    def _gen_keypair(self, metadata, spec=None):
        """ Generate a keypair according to the given client medata
        and key specification.

        :param metadata: The client metadata to generate keys for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param spec: The key specification to follow when creating the
                     keys. This should be an XML document that only
                     contains key specification data that applies to
                     the given client metadata, and may be obtained by
                     doing ``self.XMLMatch(metadata)``
        :type spec: lxml.etree._Element
        :returns: tuple - (private key data, public key data)
        """
        if spec is None:
            spec = self.XMLMatch(metadata)

        # set key parameters
        ktype = "rsa"
        bits = None
        params = spec.find("Params")
        if params is not None:
            bits = params.get("bits")
            ktype = params.get("type", ktype)
        try:
            passphrase = spec.find("Passphrase").text
        except AttributeError:
            passphrase = ''
        tempdir = tempfile.mkdtemp()
        try:
            filename = os.path.join(tempdir, "privkey")

            # generate key pair
            cmd = ["ssh-keygen", "-f", filename, "-t", ktype]
            if bits:
                cmd.extend(["-b", bits])
            cmd.append("-N")
            log_cmd = cmd[:]
            cmd.append(passphrase)
            if passphrase:
                log_cmd.append("******")
            else:
                log_cmd.append("''")
            self.debug_log("Cfg: Generating new SSH key pair: %s" %
                           " ".join(log_cmd))
            result = self.cmd.run(cmd)
            if not result.success:
                raise CfgCreationError("Cfg: Failed to generate SSH key pair "
                                       "at %s for %s: %s" %
                                       (filename, metadata.hostname,
                                        result.error))
            elif result.stderr:
                self.logger.warning("Cfg: Generated SSH key pair at %s for %s "
                                    "with errors: %s" % (filename,
                                                         metadata.hostname,
                                                         result.stderr))
            return (open(filename).read(), open(filename + ".pub").read())
        finally:
            shutil.rmtree(tempdir)

    # pylint: disable=W0221
    def create_data(self, entry, metadata):
        """ Create data for the given entry on the given client

        :param entry: The abstract entry to create data for.  This
                      will not be modified
        :type entry: lxml.etree._Element
        :param metadata: The client metadata to create data for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :returns: string - The private key data
        """
        spec = self.XMLMatch(metadata)
        specificity = self.get_specificity(metadata)
        privkey, pubkey = self._gen_keypair(metadata, spec)

        # write the public key, stripping the comment and
        # replacing it with a comment that specifies the filename.
        kdata = pubkey.split()[:2]
        kdata.append(self.pubkey_creator.get_filename(**specificity))
        pubkey = " ".join(kdata) + "\n"
        self.pubkey_creator.write_data(pubkey, **specificity)

        # encrypt the private key, write to the proper place, and
        # return it
        self.write_data(privkey, **specificity)
        return privkey
    # pylint: enable=W0221
