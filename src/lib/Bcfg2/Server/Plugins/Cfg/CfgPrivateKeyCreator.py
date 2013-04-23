""" The CfgPrivateKeyCreator creates SSH keys on the fly. """

import os
import shutil
import tempfile
import subprocess
from Bcfg2.Server.Plugin import PluginExecutionError, StructFile
from Bcfg2.Server.Plugins.Cfg import CfgCreator, CfgCreationError, SETUP
from Bcfg2.Server.Plugins.Cfg.CfgPublicKeyCreator import CfgPublicKeyCreator
try:
    import Bcfg2.Encryption
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
    __init__.__doc__ = CfgCreator.__init__.__doc__

    @property
    def category(self):
        """ The name of the metadata category that generated keys are
        specific to """
        if (SETUP.cfp.has_section("sshkeys") and
            SETUP.cfp.has_option("sshkeys", "category")):
            return SETUP.cfp.get("sshkeys", "category")
        return None

    @property
    def passphrase(self):
        """ The passphrase used to encrypt private keys """
        if (HAS_CRYPTO and
            SETUP.cfp.has_section("sshkeys") and
            SETUP.cfp.has_option("sshkeys", "passphrase")):
            return Bcfg2.Encryption.get_passphrases(SETUP)[
                SETUP.cfp.get("sshkeys", "passphrase")]
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
        :returns: string - The filename of the private key
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
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            err = proc.communicate()[1]
            if proc.wait():
                raise CfgCreationError("Cfg: Failed to generate SSH key pair "
                                       "at %s for %s: %s" %
                                       (filename, metadata.hostname, err))
            elif err:
                self.logger.warning("Cfg: Generated SSH key pair at %s for %s "
                                    "with errors: %s" % (filename,
                                                         metadata.hostname,
                                                         err))
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
                privkey = Bcfg2.Encryption.ssl_encrypt(
                    privkey,
                    self.passphrase,
                    algorithm=Bcfg2.Encryption.get_algorithm(SETUP))
                specificity['ext'] = '.crypt'

            self.write_data(privkey, **specificity)

            if return_pair:
                return (pubkey, privkey)
            else:
                return privkey
        finally:
            shutil.rmtree(os.path.dirname(filename))
    # pylint: enable=W0221

    def Index(self):
        StructFile.Index(self)
        if HAS_CRYPTO:
            strict = self.xdata.get(
                "decrypt",
                SETUP.cfp.get(Bcfg2.Encryption.CFG_SECTION, "decrypt",
                              default="strict")) == "strict"
            for el in self.xdata.xpath("//*[@encrypted]"):
                try:
                    el.text = self._decrypt(el).encode('ascii',
                                                       'xmlcharrefreplace')
                except UnicodeDecodeError:
                    self.logger.info("Cfg: Decrypted %s to gibberish, skipping"
                                     % el.tag)
                except Bcfg2.Encryption.EVPError:
                    msg = "Cfg: Failed to decrypt %s element in %s" % \
                        (el.tag, self.name)
                    if strict:
                        raise PluginExecutionError(msg)
                    else:
                        self.logger.warning(msg)
    Index.__doc__ = StructFile.Index.__doc__

    def _decrypt(self, element):
        """ Decrypt a single encrypted element """
        if not element.text or not element.text.strip():
            return
        passes = Bcfg2.Encryption.get_passphrases(SETUP)
        try:
            passphrase = passes[element.get("encrypted")]
            try:
                return Bcfg2.Encryption.ssl_decrypt(
                    element.text,
                    passphrase,
                    algorithm=Bcfg2.Encryption.get_algorithm(SETUP))
            except Bcfg2.Encryption.EVPError:
                # error is raised below
                pass
        except KeyError:
            # bruteforce_decrypt raises an EVPError with a sensible
            # error message, so we just let it propagate up the stack
            return Bcfg2.Encryption.bruteforce_decrypt(
                element.text,
                passphrases=passes.values(),
                algorithm=Bcfg2.Encryption.get_algorithm(SETUP))
        raise Bcfg2.Encryption.EVPError("Failed to decrypt")
