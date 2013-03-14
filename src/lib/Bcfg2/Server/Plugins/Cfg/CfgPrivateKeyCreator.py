""" The CfgPrivateKeyCreator creates SSH keys on the fly. """

import os
import shutil
import tempfile
from Bcfg2.Utils import Executor
from Bcfg2.Options import get_option_parser
from Bcfg2.Server.Plugin import StructFile
from Bcfg2.Server.Plugins.Cfg import CfgCreator, CfgCreationError
from Bcfg2.Server.Plugins.Cfg.CfgPublicKeyCreator import CfgPublicKeyCreator
try:
    from Bcfg2.Server.Encryption import get_passphrases, ssl_encrypt
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


class CfgPrivateKeyCreator(CfgCreator, StructFile):
    """The CfgPrivateKeyCreator creates SSH keys on the fly. """

    #: Different configurations for different clients/groups can be
    #: handled with Client and Group tags within privkey.xml
    __specific__ = False

    #: Handle XML specifications of private keys
    __basenames__ = ['privkey.xml']

    def __init__(self, fname):
        CfgCreator.__init__(self, fname)
        StructFile.__init__(self, fname)

        pubkey_path = os.path.dirname(self.name) + ".pub"
        pubkey_name = os.path.join(pubkey_path, os.path.basename(pubkey_path))
        self.pubkey_creator = CfgPublicKeyCreator(pubkey_name)
        self.setup = get_option_parser()
        self.cmd = Executor()
    __init__.__doc__ = CfgCreator.__init__.__doc__

    @property
    def category(self):
        """ The name of the metadata category that generated keys are
        specific to """
        if (self.setup.cfp.has_section("sshkeys") and
            self.setup.cfp.has_option("sshkeys", "category")):
            return self.setup.cfp.get("sshkeys", "category")
        return None

    @property
    def passphrase(self):
        """ The passphrase used to encrypt private keys """
        if (HAS_CRYPTO and
            self.setup.cfp.has_section("sshkeys") and
            self.setup.cfp.has_option("sshkeys", "passphrase")):
            return get_passphrases()[self.setup.cfp.get("sshkeys",
                                                        "passphrase")]
        return None

    def handle_event(self, event):
        CfgCreator.handle_event(self, event)
        StructFile.HandleEvent(self, event)
    handle_event.__doc__ = CfgCreator.handle_event.__doc__

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
        :returns: None
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
            return filename
        except:
            shutil.rmtree(tempdir)
            raise

    def get_specificity(self, metadata, spec=None):
        """ Get config settings for key generation specificity
        (per-host or per-group).

        :param metadata: The client metadata to create data for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param spec: The key specification to follow when creating the
                     keys. This should be an XML document that only
                     contains key specification data that applies to
                     the given client metadata, and may be obtained by
                     doing ``self.XMLMatch(metadata)``
        :type spec: lxml.etree._Element
        :returns: dict - A dict of specificity arguments suitable for
                  passing to
                  :func:`Bcfg2.Server.Plugins.Cfg.CfgCreator.write_data`
                  or
                  :func:`Bcfg2.Server.Plugins.Cfg.CfgCreator.get_filename`
        """
        if spec is None:
            spec = self.XMLMatch(metadata)
        category = spec.get("category", self.category)
        print("category=%s" % category)
        if category is None:
            per_host_default = "true"
        else:
            per_host_default = "false"
        per_host = spec.get("perhost", per_host_default).lower() == "true"

        specificity = dict(host=metadata.hostname)
        if category and not per_host:
            group = metadata.group_in_category(category)
            if group:
                specificity = dict(group=group,
                                   prio=int(spec.get("priority", 50)))
            else:
                self.logger.info("Cfg: %s has no group in category %s, "
                                 "creating host-specific key" %
                                 (metadata.hostname, category))
        return specificity

    # pylint: disable=W0221
    def create_data(self, entry, metadata, return_pair=False):
        """ Create data for the given entry on the given client

        :param entry: The abstract entry to create data for.  This
                      will not be modified
        :type entry: lxml.etree._Element
        :param metadata: The client metadata to create data for
        :type metadata: Bcfg2.Server.Plugins.Metadata.ClientMetadata
        :param return_pair: Return a tuple of ``(public key, private
                            key)`` instead of just the private key.
                            This is used by
                            :class:`Bcfg2.Server.Plugins.Cfg.CfgPublicKeyCreator.CfgPublicKeyCreator`
                            to create public keys as requested.
        :type return_pair: bool
        :returns: string - The private key data
        :returns: tuple - Tuple of ``(public key, private key)``, if
                  ``return_pair`` is set to True
        """
        spec = self.XMLMatch(metadata)
        specificity = self.get_specificity(metadata, spec)
        filename = self._gen_keypair(metadata, spec)

        try:
            # write the public key, stripping the comment and
            # replacing it with a comment that specifies the filename.
            kdata = open(filename + ".pub").read().split()[:2]
            kdata.append(self.pubkey_creator.get_filename(**specificity))
            pubkey = " ".join(kdata) + "\n"
            self.pubkey_creator.write_data(pubkey, **specificity)

            # encrypt the private key, write to the proper place, and
            # return it
            privkey = open(filename).read()
            if HAS_CRYPTO and self.passphrase:
                self.debug_log("Cfg: Encrypting key data at %s" % filename)
                privkey = ssl_encrypt(privkey, self.passphrase)
                specificity['ext'] = '.crypt'

            self.write_data(privkey, **specificity)

            if return_pair:
                return (pubkey, privkey)
            else:
                return privkey
        finally:
            shutil.rmtree(os.path.dirname(filename))
    # pylint: enable=W0221
