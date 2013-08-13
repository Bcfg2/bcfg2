""" Cfg creator that creates SSL certs """

import os
import sys
import tempfile
import lxml.etree
import Bcfg2.Options
from Bcfg2.Utils import Executor
from Bcfg2.Compat import ConfigParser
from Bcfg2.Server.FileMonitor import get_fam
from Bcfg2.Server.Plugin import PluginExecutionError
from Bcfg2.Server.Plugins.Cfg import CfgCreationError, XMLCfgCreator, \
    CfgCreator, CfgVerifier, CfgVerificationError, get_cfg


class CfgSSLCACertCreator(XMLCfgCreator, CfgVerifier):
    """ This class acts as both a Cfg creator that creates SSL certs,
    and as a Cfg verifier that verifies SSL certs. """

    #: Different configurations for different clients/groups can be
    #: handled with Client and Group tags within pubkey.xml
    __specific__ = False

    #: Handle XML specifications of private keys
    __basenames__ = ['sslcert.xml']

    cfg_section = "sslca"
    options = [
        Bcfg2.Options.Option(
            cf=("sslca", "category"), dest="sslca_category",
            help="Metadata category that generated SSL keys are specific to"),
        Bcfg2.Options.Option(
            cf=("sslca", "passphrase"), dest="sslca_passphrase",
            help="Passphrase used to encrypt generated SSL keys"),
        Bcfg2.Options.WildcardSectionGroup(
            Bcfg2.Options.PathOption(
                cf=("sslca_*", "config"),
                help="Path to the openssl config for the CA"),
            Bcfg2.Options.Option(
                cf=("sslca_*", "passphrase"),
                help="Passphrase for the CA private key"),
            Bcfg2.Options.PathOption(
                cf=("sslca_*", "chaincert"),
                help="Path to the SSL chaining certificate for verification"),
            Bcfg2.Options.BooleanOption(
                cf=("sslca_*", "root_ca"),
                help="Whether or not <chaincert> is a root CA (as opposed to "
                "an intermediate cert"),
            prefix="")]

    def __init__(self, fname):
        XMLCfgCreator.__init__(self, fname)
        CfgVerifier.__init__(self, fname, None)
        self.cmd = Executor()
        self.cfg = get_cfg()

    def build_req_config(self, metadata):
        """ Generates a temporary openssl configuration file that is
        used to generate the required certificate request. """
        fd, fname = tempfile.mkstemp()
        cfp = ConfigParser.ConfigParser({})
        cfp.optionxform = str
        defaults = dict(
            req=dict(
                default_md='sha1',
                distinguished_name='req_distinguished_name',
                req_extensions='v3_req',
                x509_extensions='v3_req',
                prompt='no'),
            req_distinguished_name=dict(),
            v3_req=dict(subjectAltName='@alt_names'),
            alt_names=dict())
        for section in list(defaults.keys()):
            cfp.add_section(section)
            for key in defaults[section]:
                cfp.set(section, key, defaults[section][key])
        spec = self.XMLMatch(metadata)
        cert = spec.find("Cert")
        altnamenum = 1
        altnames = spec.findall('subjectAltName')
        altnames.extend(list(metadata.aliases))
        altnames.append(metadata.hostname)
        for altname in altnames:
            cfp.set('alt_names', 'DNS.' + str(altnamenum), altname)
            altnamenum += 1
        for item in ['C', 'L', 'ST', 'O', 'OU', 'emailAddress']:
            if cert.get(item):
                cfp.set('req_distinguished_name', item, cert.get(item))
        cfp.set('req_distinguished_name', 'CN', metadata.hostname)
        self.debug_log("Cfg: Writing temporary CSR config to %s" % fname)
        try:
            cfp.write(os.fdopen(fd, 'w'))
        except IOError:
            raise CfgCreationError("Cfg: Failed to write temporary CSR config "
                                   "file: %s" % sys.exc_info()[1])
        return fname

    def build_request(self, keyfile, metadata):
        """ Create the certificate request """
        req_config = self.build_req_config(metadata)
        try:
            fd, req = tempfile.mkstemp()
            os.close(fd)
            cert = self.XMLMatch(metadata).find("Cert")
            days = cert.get("days", "365")
            cmd = ["openssl", "req", "-new", "-config", req_config,
                   "-days", days, "-key", keyfile, "-text", "-out", req]
            result = self.cmd.run(cmd)
            if not result.success:
                raise CfgCreationError("Failed to generate CSR: %s" %
                                       result.error)
            return req
        finally:
            try:
                os.unlink(req_config)
            except OSError:
                self.logger.error("Cfg: Failed to unlink temporary CSR "
                                  "config: %s" % sys.exc_info()[1])

    def get_ca(self, name):
        """ get a dict describing a CA from the config file """
        rv = dict()
        prefix = "sslca_%s_" % name
        for attr in dir(Bcfg2.Options.setup):
            if attr.startswith(prefix):
                rv[attr[len(prefix):]] = getattr(Bcfg2.Options.setup, attr)
        return rv

    def create_data(self, entry, metadata):
        """ generate a new cert """
        self.logger.info("Cfg: Generating new SSL cert for %s" % self.name)
        cert = self.XMLMatch(metadata).find("Cert")
        ca = self.get_ca(cert.get('ca', 'default'))
        req = self.build_request(self._get_keyfile(cert, metadata), metadata)
        try:
            days = cert.get('days', '365')
            cmd = ["openssl", "ca", "-config", ca['config'], "-in", req,
                   "-days", days, "-batch"]
            passphrase = ca.get('passphrase')
            if passphrase:
                cmd.extend(["-passin", "pass:%s" % passphrase])
            result = self.cmd.run(cmd)
            if not result.success:
                raise CfgCreationError("Failed to generate cert: %s" %
                                       result.error)
        except KeyError:
            raise CfgCreationError("Cfg: [sslca_%s] section has no 'config' "
                                   "option" % cert.get('ca', 'default'))
        finally:
            try:
                os.unlink(req)
            except OSError:
                self.logger.error("Cfg: Failed to unlink temporary CSR: %s " %
                                  sys.exc_info()[1])
        data = result.stdout
        if cert.get('append_chain') and 'chaincert' in ca:
            data += open(ca['chaincert']).read()

        self.write_data(data, **self.get_specificity(metadata))
        return data

    def verify_entry(self, entry, metadata, data):
        fd, fname = tempfile.mkstemp()
        self.debug_log("Cfg: Writing SSL cert %s to temporary file %s for "
                       "verification" % (entry.get("name"), fname))
        os.fdopen(fd, 'w').write(data)
        cert = self.XMLMatch(metadata).find("Cert")
        ca = self.get_ca(cert.get('ca', 'default'))
        try:
            if ca.get('chaincert'):
                self.verify_cert_against_ca(fname, entry, metadata)
            self.verify_cert_against_key(fname,
                                         self._get_keyfile(cert, metadata))
        finally:
            os.unlink(fname)

    def _get_keyfile(self, cert, metadata):
        """ Given a <Cert/> element and client metadata, return the
        full path to the file on the filesystem that the key lives in."""
        keypath = cert.get("key")
        eset = self.cfg.entries[keypath]
        try:
            return eset.best_matching(metadata).name
        except PluginExecutionError:
            # SSL key needs to be created
            try:
                creator = eset.best_matching(metadata,
                                             eset.get_handlers(metadata,
                                                               CfgCreator))
            except PluginExecutionError:
                raise CfgCreationError("Cfg: No SSL key or key creator "
                                       "defined for %s" % keypath)

            keyentry = lxml.etree.Element("Path", name=keypath)
            creator.create_data(keyentry, metadata)

            tries = 0
            while True:
                if tries >= 10:
                    raise CfgCreationError("Cfg: Timed out waiting for event "
                                           "on SSL key at %s" % keypath)
                get_fam().handle_events_in_interval(1)
                try:
                    return eset.best_matching(metadata).name
                except PluginExecutionError:
                    tries += 1
                    continue

    def verify_cert_against_ca(self, filename, entry, metadata):
        """
        check that a certificate validates against the ca cert,
        and that it has not expired.
        """
        cert = self.XMLMatch(metadata).find("Cert")
        ca = self.get_ca(cert.get("ca", "default"))
        chaincert = ca.get('chaincert')
        cmd = ["openssl", "verify"]
        is_root = ca.get('root_ca', "false").lower() == 'true'
        if is_root:
            cmd.append("-CAfile")
        else:
            # verifying based on an intermediate cert
            cmd.extend(["-purpose", "sslserver", "-untrusted"])
        cmd.extend([chaincert, filename])
        self.debug_log("Cfg: Verifying %s against CA" % entry.get("name"))
        result = self.cmd.run(cmd)
        if result.stdout == cert + ": OK\n":
            self.debug_log("Cfg: %s verified successfully against CA" %
                           entry.get("name"))
        else:
            raise CfgVerificationError("%s failed verification against CA: %s"
                                       % (entry.get("name"), result.error))

    def _get_modulus(self, fname, ftype="x509"):
        """ get the modulus from the given file """
        cmd = ["openssl", ftype, "-noout", "-modulus", "-in", fname]
        self.debug_log("Cfg: Getting modulus of %s for verification: %s" %
                       (fname, " ".join(cmd)))
        result = self.cmd.run(cmd)
        if not result.success:
            raise CfgVerificationError("Failed to get modulus of %s: %s" %
                                       (fname, result.error))
        return result.stdout.strip()

    def verify_cert_against_key(self, filename, keyfile):
        """ check that a certificate validates against its private
        key. """
        cert = self._get_modulus(filename)
        key = self._get_modulus(keyfile, ftype="rsa")
        if cert == key:
            self.debug_log("Cfg: %s verified successfully against key %s" %
                           (filename, keyfile))
        else:
            raise CfgVerificationError("%s failed verification against key %s"
                                       % (filename, keyfile))
