import Bcfg2.Server.Plugin
import Bcfg2.Options
import lxml.etree
import posixpath
import tempfile
import os
from subprocess import Popen, PIPE, STDOUT
# Compatibility import
from Bcfg2.Bcfg2Py3k import ConfigParser

try:
    from hashlib import md5
except ImportError:
    from md5 import md5

class SSLCA(Bcfg2.Server.Plugin.GroupSpool):
    """
    The SSLCA generator handles the creation and
    management of ssl certificates and their keys.
    """
    name = 'SSLCA'
    __version__ = '$Id:$'
    __author__ = 'g.hagger@gmail.com'
    __child__ = Bcfg2.Server.Plugin.FileBacked
    key_specs = {}
    cert_specs = {}
    CAs = {}

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.GroupSpool.__init__(self, core, datastore)
        self.infoxml = dict()

    def HandleEvent(self, event=None):
        """
        Updates which files this plugin handles based upon filesystem events.
        Allows configuration items to be added/removed without server restarts.
        """
        action = event.code2str()
        if event.filename[0] == '/':
            return
        epath = "".join([self.data, self.handles[event.requestID],
                         event.filename])
        if posixpath.isdir(epath):
            ident = self.handles[event.requestID] + event.filename
        else:
            ident = self.handles[event.requestID][:-1]

        fname = os.path.join(ident, event.filename)

        if event.filename.endswith('.xml'):
            if action in ['exists', 'created', 'changed']:
                if event.filename.endswith('key.xml'):
                    key_spec = dict(list(lxml.etree.parse(epath,
                                                          parser=Bcfg2.Server.XMLParser).find('Key').items()))
                    self.key_specs[ident] = {
                        'bits': key_spec.get('bits', 2048),
                        'type': key_spec.get('type', 'rsa')
                    }
                    self.Entries['Path'][ident] = self.get_key
                elif event.filename.endswith('cert.xml'):
                    cert_spec = dict(list(lxml.etree.parse(epath,
                                                           parser=Bcfg2.Server.XMLParser).find('Cert').items()))
                    ca = cert_spec.get('ca', 'default')
                    self.cert_specs[ident] = {
                        'ca': ca,
                        'format': cert_spec.get('format', 'pem'),
                        'key': cert_spec.get('key'),
                        'days': cert_spec.get('days', 365),
                        'C': cert_spec.get('c'),
                        'L': cert_spec.get('l'),
                        'ST': cert_spec.get('st'),
                        'OU': cert_spec.get('ou'),
                        'O': cert_spec.get('o'),
                        'emailAddress': cert_spec.get('emailaddress')
                    }
                    cp = ConfigParser.ConfigParser()
                    cp.read(self.core.cfile)
                    self.CAs[ca] = dict(cp.items('sslca_' + ca))
                    self.Entries['Path'][ident] = self.get_cert
                elif event.filename.endswith("info.xml"):
                    self.infoxml[ident] = Bcfg2.Server.Plugin.InfoXML(epath,
                                                                      noprio=True)
                    self.infoxml[ident].HandleEvent(event)
            if action == 'deleted':
                if ident in self.Entries['Path']:
                    del self.Entries['Path'][ident]
        else:
            if action in ['exists', 'created']:
                if posixpath.isdir(epath):
                    self.AddDirectoryMonitor(epath[len(self.data):])
                if ident not in self.entries and posixpath.isfile(epath):
                    self.entries[fname] = self.__child__(epath)
                    self.entries[fname].HandleEvent(event)
            if action == 'changed':
                self.entries[fname].HandleEvent(event)
            elif action == 'deleted':
                if fname in self.entries:
                    del self.entries[fname]
                else:
                    self.entries[fname].HandleEvent(event)

    def get_key(self, entry, metadata):
        """
        either grabs a prexisting key hostfile, or triggers the generation
        of a new key if one doesn't exist.
        """
        # check if we already have a hostfile, or need to generate a new key
        # TODO: verify key fits the specs
        path = entry.get('name')
        filename = os.path.join(path, "%s.H_%s" % (os.path.basename(path),
                                                   metadata.hostname))
        if filename not in list(self.entries.keys()):
            key = self.build_key(filename, entry, metadata)
            open(self.data + filename, 'w').write(key)
            entry.text = key
            self.entries[filename] = self.__child__(self.data + filename)
            self.entries[filename].HandleEvent()
        else:
            entry.text = self.entries[filename].data

        entry.set("type", "file")
        if path in self.infoxml:
            Bcfg2.Server.Plugin.bind_info(entry, metadata,
                                          infoxml=self.infoxml[path])
        else:
            Bcfg2.Server.Plugin.bind_info(entry, metadata)

    def build_key(self, filename, entry, metadata):
        """
        generates a new key according the the specification
        """
        type = self.key_specs[entry.get('name')]['type']
        bits = self.key_specs[entry.get('name')]['bits']
        if type == 'rsa':
            cmd = ["openssl", "genrsa", bits]
        elif type == 'dsa':
            cmd = ["openssl", "dsaparam", "-noout", "-genkey", bits]
        key = Popen(cmd, stdout=PIPE).stdout.read()
        return key

    def get_cert(self, entry, metadata):
        """
        either grabs a prexisting cert hostfile, or triggers the generation
        of a new cert if one doesn't exist.
        """
        path = entry.get('name')
        filename = os.path.join(path, "%s.H_%s" % (os.path.basename(path),
                                                   metadata.hostname))

        # first - ensure we have a key to work with
        key = self.cert_specs[entry.get('name')].get('key')
        key_filename = os.path.join(key, "%s.H_%s" % (os.path.basename(key),
                                                      metadata.hostname))
        if key_filename not in self.entries:
            e = lxml.etree.Element('Path')
            e.set('name', key)
            self.core.Bind(e, metadata)

        # check if we have a valid hostfile
        if (filename in list(self.entries.keys()) and 
            self.verify_cert(filename, key_filename, entry)):
            entry.text = self.entries[filename].data
        else:
            cert = self.build_cert(key_filename, entry, metadata)
            open(self.data + filename, 'w').write(cert)
            self.entries[filename] = self.__child__(self.data + filename)
            self.entries[filename].HandleEvent()
            entry.text = cert

        entry.set("type", "file")
        if path in self.infoxml:
            Bcfg2.Server.Plugin.bind_info(entry, metadata,
                                          infoxml=self.infoxml[path])
        else:
            Bcfg2.Server.Plugin.bind_info(entry, metadata)

    def verify_cert(self, filename, key_filename, entry):
        do_verify = self.CAs[self.cert_specs[entry.get('name')]['ca']].get('verify_certs', True)
        if do_verify:
            return (self.verify_cert_against_ca(filename, entry) and
                    self.verify_cert_against_key(filename, key_filename))
        return True

    def verify_cert_against_ca(self, filename, entry):
        """
        check that a certificate validates against the ca cert,
        and that it has not expired.
        """
        ca = self.CAs[self.cert_specs[entry.get('name')]['ca']]
        chaincert = ca.get('chaincert')
        cert = self.data + filename
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

    def verify_cert_against_key(self, filename, key_filename):
        """
        check that a certificate validates against its private key.
        """
        cert = self.data + filename
        key = self.data + key_filename
        cert_md5 = \
            md5(Popen(["openssl", "x509", "-noout", "-modulus", "-in", cert],
                      stdout=PIPE,
                      stderr=STDOUT).stdout.read().strip()).hexdigest()
        key_md5 = \
            md5(Popen(["openssl", "rsa", "-noout", "-modulus", "-in", key],
                      stdout=PIPE,
                      stderr=STDOUT).stdout.read().strip()).hexdigest()
        if cert_md5 == key_md5:
            self.debug_log("SSLCA: %s verified successfully against key %s" %
                           (filename, key_filename))
            return True
        self.logger.warning("SSLCA: %s failed verification against key %s" %
                            (filename, key_filename))
        return False

    def build_cert(self, key_filename, entry, metadata):
        """
        creates a new certificate according to the specification
        """
        req_config = self.build_req_config(entry, metadata)
        req = self.build_request(key_filename, req_config, entry)
        ca = self.cert_specs[entry.get('name')]['ca']
        ca_config = self.CAs[ca]['config']
        days = self.cert_specs[entry.get('name')]['days']
        passphrase = self.CAs[ca].get('passphrase')
        cmd = ["openssl", "ca", "-config", ca_config, "-in", req,
               "-days", days, "-batch"]
        if passphrase:
            cmd.extend(["-passin", "pass:%s" % passphrase])
        cert = Popen(cmd, stdout=PIPE).stdout.read()
        try:
            os.unlink(req_config)
            os.unlink(req)
        except OSError:
            self.logger.error("Failed to unlink temporary files")
        return cert

    def build_req_config(self, entry, metadata):
        """
        generates a temporary openssl configuration file that is
        used to generate the required certificate request
        """
        # create temp request config file
        conffile = open(tempfile.mkstemp()[1], 'w')
        cp = ConfigParser.ConfigParser({})
        cp.optionxform = str
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
            cp.add_section(section)
            for key in defaults[section]:
                cp.set(section, key, defaults[section][key])
        x = 1
        altnames = list(metadata.aliases)
        altnames.append(metadata.hostname)
        for altname in altnames:
            cp.set('alt_names', 'DNS.' + str(x), altname)
            x += 1
        for item in ['C', 'L', 'ST', 'O', 'OU', 'emailAddress']:
            if self.cert_specs[entry.get('name')][item]:
                cp.set('req_distinguished_name', item, self.cert_specs[entry.get('name')][item])
        cp.set('req_distinguished_name', 'CN', metadata.hostname)
        cp.write(conffile)
        conffile.close()
        return conffile.name

    def build_request(self, key_filename, req_config, entry):
        """
        creates the certificate request
        """
        req = tempfile.mkstemp()[1]
        days = self.cert_specs[entry.get('name')]['days']
        key = self.data + key_filename
        cmd = ["openssl", "req", "-new", "-config", req_config,
               "-days", days, "-key", key, "-text", "-out", req]
        res = Popen(cmd, stdout=PIPE).stdout.read()
        return req
