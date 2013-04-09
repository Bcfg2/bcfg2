""" The SSLCA generator handles the creation and management of ssl
certificates and their keys. """

import os
import sys
import logging
import tempfile
import lxml.etree
from subprocess import Popen, PIPE, STDOUT
import Bcfg2.Options
import Bcfg2.Server.Plugin
from Bcfg2.Compat import ConfigParser
from Bcfg2.Server.Plugin import PluginExecutionError

LOGGER = logging.getLogger(__name__)


class SSLCAXMLSpec(Bcfg2.Server.Plugin.StructFile):
    """ Base class to handle key.xml and cert.xml """
    attrs = dict()
    tag = None

    def get_spec(self, metadata):
        """ Get a specification for the type of object described by
        this SSLCA XML file for the given client metadata object """
        entries = [e for e in self.Match(metadata) if e.tag == self.tag]
        if len(entries) == 0:
            raise PluginExecutionError("No matching %s entry found for %s "
                                       "in %s" % (self.tag,
                                                  metadata.hostname,
                                                  self.name))
        elif len(entries) > 1:
            LOGGER.warning("More than one matching %s entry found for %s in "
                           "%s; using first match" % (self.tag,
                                                      metadata.hostname,
                                                      self.name))
        rv = dict()
        for attr, default in self.attrs.items():
            val = entries[0].get(attr.lower(), default)
            if default in ['true', 'false']:
                rv[attr] = val == 'true'
            else:
                rv[attr] = val
        return rv


class SSLCAKeySpec(SSLCAXMLSpec):
    """ Handle key.xml files """
    attrs = dict(bits='2048', type='rsa')
    tag = 'Key'


class SSLCACertSpec(SSLCAXMLSpec):
    """ Handle cert.xml files """
    attrs = dict(ca='default',
                 format='pem',
                 key=None,
                 days='365',
                 C=None,
                 L=None,
                 ST=None,
                 OU=None,
                 O=None,
                 emailAddress=None,
                 append_chain='false')
    tag = 'Cert'

    def get_spec(self, metadata):
        rv = SSLCAXMLSpec.get_spec(self, metadata)
        rv['subjectaltname'] = [e.text for e in self.Match(metadata)
                                if e.tag == "subjectAltName"]
        return rv


class SSLCADataFile(Bcfg2.Server.Plugin.SpecificData):
    """ Handle key and cert files """
    def bind_entry(self, entry, _):
        """ Bind the data in the file to the given abstract entry """
        entry.text = self.data
        entry.set("type", "file")
        return entry


class SSLCAEntrySet(Bcfg2.Server.Plugin.EntrySet):
    """ Entry set to handle SSLCA entries and XML files """
    def __init__(self, _, path, entry_type, encoding, parent=None):
        Bcfg2.Server.Plugin.EntrySet.__init__(self, os.path.basename(path),
                                              path, entry_type, encoding)
        self.parent = parent
        self.key = None
        self.cert = None

    def handle_event(self, event):
        action = event.code2str()
        fpath = os.path.join(self.path, event.filename)

        if event.filename == 'key.xml':
            if action in ['exists', 'created', 'changed']:
                self.key = SSLCAKeySpec(fpath)
            self.key.HandleEvent(event)
        elif event.filename == 'cert.xml':
            if action in ['exists', 'created', 'changed']:
                self.cert = SSLCACertSpec(fpath)
            self.cert.HandleEvent(event)
        else:
            Bcfg2.Server.Plugin.EntrySet.handle_event(self, event)

    def build_key(self, entry, metadata):
        """
        either grabs a prexisting key hostfile, or triggers the generation
        of a new key if one doesn't exist.
        """
        # TODO: verify key fits the specs
        filename = "%s.H_%s" % (os.path.basename(entry.get('name')),
                                metadata.hostname)
        self.logger.info("SSLCA: Generating new key %s" % filename)
        key_spec = self.key.get_spec(metadata)
        ktype = key_spec['type']
        bits = key_spec['bits']
        if ktype == 'rsa':
            cmd = ["openssl", "genrsa", bits]
        elif ktype == 'dsa':
            cmd = ["openssl", "dsaparam", "-noout", "-genkey", bits]
        self.debug_log("SSLCA: Generating new key: %s" % " ".join(cmd))
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        key, err = proc.communicate()
        if proc.wait():
            raise PluginExecutionError("SSLCA: Failed to generate key %s for "
                                       "%s: %s" % (entry.get("name"),
                                                   metadata.hostname, err))
        open(os.path.join(self.path, filename), 'w').write(key)
        return key

    def build_cert(self, entry, metadata, keyfile):
        """ generate a new cert """
        filename = "%s.H_%s" % (os.path.basename(entry.get('name')),
                                metadata.hostname)
        self.logger.info("SSLCA: Generating new cert %s" % filename)
        cert_spec = self.cert.get_spec(metadata)
        ca = self.parent.get_ca(cert_spec['ca'])
        req_config = None
        req = None
        try:
            req_config = self.build_req_config(metadata)
            req = self.build_request(keyfile, req_config, metadata)
            days = cert_spec['days']
            cmd = ["openssl", "ca", "-config", ca['config'], "-in", req,
                   "-days", days, "-batch"]
            passphrase = ca.get('passphrase')
            if passphrase:
                cmd.extend(["-passin", "pass:%s" % passphrase])

                def _scrub_pass(arg):
                    """ helper to scrub the passphrase from the
                    argument list """
                    if arg.startswith("pass:"):
                        return "pass:******"
                    else:
                        return arg
            else:
                _scrub_pass = lambda a: a

            self.debug_log("SSLCA: Generating new certificate: %s" %
                           " ".join(_scrub_pass(a) for a in cmd))
            proc = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
            (cert, err) = proc.communicate()
            if proc.wait():
                # pylint: disable=E1103
                raise PluginExecutionError("SSLCA: Failed to generate cert: %s"
                                           % err.splitlines()[-1])
                # pylint: enable=E1103
        finally:
            try:
                if req_config and os.path.exists(req_config):
                    os.unlink(req_config)
                if req and os.path.exists(req):
                    os.unlink(req)
            except OSError:
                self.logger.error("SSLCA: Failed to unlink temporary files: %s"
                                  % sys.exc_info()[1])
        if cert_spec['append_chain'] and 'chaincert' in ca:
            cert += open(ca['chaincert']).read()

        open(os.path.join(self.path, filename), 'w').write(cert)
        return cert

    def build_req_config(self, metadata):
        """
        generates a temporary openssl configuration file that is
        used to generate the required certificate request
        """
        # create temp request config file
        fd, fname = tempfile.mkstemp()
        cfp = ConfigParser.ConfigParser({})
        cfp.optionxform = str
        defaults = {
            'req': {
                'default_md': 'sha1',
                'distinguished_name': 'req_distinguished_name',
                'req_extensions': 'v3_req',
                'x509_extensions': 'v3_req',
                'prompt': 'no'
            },
            'req_distinguished_name': {},
            'v3_req': {
                'subjectAltName': '@alt_names'
            },
            'alt_names': {}
        }
        for section in list(defaults.keys()):
            cfp.add_section(section)
            for key in defaults[section]:
                cfp.set(section, key, defaults[section][key])
        cert_spec = self.cert.get_spec(metadata)
        altnamenum = 1
        altnames = cert_spec['subjectaltname']
        altnames.extend(list(metadata.aliases))
        altnames.append(metadata.hostname)
        for altname in altnames:
            cfp.set('alt_names', 'DNS.' + str(altnamenum), altname)
            altnamenum += 1
        for item in ['C', 'L', 'ST', 'O', 'OU', 'emailAddress']:
            if cert_spec[item]:
                cfp.set('req_distinguished_name', item, cert_spec[item])
        cfp.set('req_distinguished_name', 'CN', metadata.hostname)
        self.debug_log("SSLCA: Writing temporary request config to %s" % fname)
        try:
            cfp.write(os.fdopen(fd, 'w'))
        except IOError:
            raise PluginExecutionError("SSLCA: Failed to write temporary CSR "
                                       "config file: %s" % sys.exc_info()[1])
        return fname

    def build_request(self, keyfile, req_config, metadata):
        """
        creates the certificate request
        """
        fd, req = tempfile.mkstemp()
        os.close(fd)
        days = self.cert.get_spec(metadata)['days']
        cmd = ["openssl", "req", "-new", "-config", req_config,
               "-days", days, "-key", keyfile, "-text", "-out", req]
        self.debug_log("SSLCA: Generating new CSR: %s" % " ".join(cmd))
        proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
        err = proc.communicate()[1]
        if proc.wait():
            raise PluginExecutionError("SSLCA: Failed to generate CSR: %s" %
                                       err)
        return req

    def verify_cert(self, filename, keyfile, entry, metadata):
        """ Perform certification verification against the CA and
        against the key """
        ca = self.parent.get_ca(self.cert.get_spec(metadata)['ca'])
        do_verify = ca.get('chaincert')
        if do_verify:
            return (self.verify_cert_against_ca(filename, entry, metadata) and
                    self.verify_cert_against_key(filename, keyfile))
        return True

    def verify_cert_against_ca(self, filename, entry, metadata):
        """
        check that a certificate validates against the ca cert,
        and that it has not expired.
        """
        ca = self.parent.get_ca(self.cert.get_spec(metadata)['ca'])
        chaincert = ca.get('chaincert')
        cert = os.path.join(self.path, filename)
        cmd = ["openssl", "verify"]
        is_root = ca.get('root_ca', "false").lower() == 'true'
        if is_root:
            cmd.append("-CAfile")
        else:
            # verifying based on an intermediate cert
            cmd.extend(["-purpose", "sslserver", "-untrusted"])
        cmd.extend([chaincert, cert])
        self.debug_log("SSLCA: Verifying %s against CA: %s" %
                       (entry.get("name"), " ".join(cmd)))
        res = Popen(cmd, stdout=PIPE, stderr=STDOUT).stdout.read()
        if res == cert + ": OK\n":
            self.debug_log("SSLCA: %s verified successfully against CA" %
                           entry.get("name"))
            return True
        self.logger.warning("SSLCA: %s failed verification against CA: %s" %
                            (entry.get("name"), res))
        return False

    def verify_cert_against_key(self, filename, keyfile):
        """
        check that a certificate validates against its private key.
        """
        def _modulus(fname, ftype="x509"):
            """ get the modulus from the given file """
            cmd = ["openssl", ftype, "-noout", "-modulus", "-in", fname]
            self.debug_log("SSLCA: Getting modulus of %s for verification: %s"
                           % (fname, " ".join(cmd)))
            proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
            rv, err = proc.communicate()
            if proc.wait():
                self.logger.warning("SSLCA: Failed to get modulus of %s: %s" %
                                    (fname, err))
            return rv.strip()  # pylint: disable=E1103

        certfile = os.path.join(self.path, filename)
        cert = _modulus(certfile)
        key = _modulus(keyfile, ftype="rsa")
        if cert == key:
            self.debug_log("SSLCA: %s verified successfully against key %s" %
                           (filename, keyfile))
            return True
        self.logger.warning("SSLCA: %s failed verification against key %s" %
                            (filename, keyfile))
        return False

    def bind_entry(self, entry, metadata):
        if self.key:
            self.bind_info_to_entry(entry, metadata)
            try:
                return self.best_matching(metadata).bind_entry(entry, metadata)
            except PluginExecutionError:
                entry.text = self.build_key(entry, metadata)
                entry.set("type", "file")
                return entry
        elif self.cert:
            key = self.cert.get_spec(metadata)['key']
            cleanup_keyfile = False
            try:
                keyfile = self.parent.entries[key].best_matching(metadata).name
            except PluginExecutionError:
                cleanup_keyfile = True
                # create a temp file with the key in it
                fd, keyfile = tempfile.mkstemp()
                os.chmod(keyfile, 384)  # 0600
                el = lxml.etree.Element('Path', name=key)
                self.parent.core.Bind(el, metadata)
                os.fdopen(fd, 'w').write(el.text)

            try:
                self.bind_info_to_entry(entry, metadata)
                try:
                    best = self.best_matching(metadata)
                    if self.verify_cert(best.name, keyfile, entry, metadata):
                        return best.bind_entry(entry, metadata)
                except PluginExecutionError:
                    pass
                # if we get here, it's because either a) there was no best
                # matching entry; or b) the existing cert did not verify
                entry.text = self.build_cert(entry, metadata, keyfile)
                entry.set("type", "file")
                return entry
            finally:
                if cleanup_keyfile:
                    try:
                        os.unlink(keyfile)
                    except OSError:
                        err = sys.exc_info()[1]
                        self.logger.error("SSLCA: Failed to unlink temporary "
                                          "key %s: %s" % (keyfile, err))


class SSLCA(Bcfg2.Server.Plugin.GroupSpool):
    """ The SSLCA generator handles the creation and management of ssl
    certificates and their keys. """
    __author__ = 'g.hagger@gmail.com'
    # python 2.5 doesn't support mixing *magic and keyword arguments
    es_cls = lambda self, *args: SSLCAEntrySet(*args, **dict(parent=self))
    es_child_cls = SSLCADataFile

    def get_ca(self, name):
        """ get a dict describing a CA from the config file """
        return dict(self.core.setup.cfp.items("sslca_%s" % name))
