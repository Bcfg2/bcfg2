import Bcfg2.Server.Plugin
import Bcfg2.Options
import os
from ConfigParser import ConfigParser, NoSectionError, NoOptionError
from M2Crypto import RSA, EVP, X509, m2

class SSLCA(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.Generator,
              Bcfg2.Server.Plugin.DirectoryBacked):
    """
        The sslca generator manages ssl certificates
        and keys
    """

    name = 'SSLbase'
    __version__ = '0.00000000001'
    __author__ = 'ghagger@wgen.net'

    hostkey = 'localhost.key'
    hostcert = 'localhost.crt'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Generator.__init__(self)
        try:
            Bcfg2.Server.Plugin.DirectoryBacked.__init__(self, self.data,
                                                         self.core.fam)
        except OSError, ioerr:
            self.logger.error("Failed to load SSLbase repository from %s" \
                              % (self.data))
            self.logger.error(ioerr)
            raise Bcfg2.Server.Plugin.PluginInitError
        self.Entries = {'Path':
                        {'/etc/pki/tls/private/localhost.key': self.get_key,
                         '/etc/pki/tls/certs/localhost.crt': self.get_cert}}
        # grab essential sslca configuration from bcfg2.conf
        cp = ConfigParser()
        cp.read(Bcfg2.Options.CFILE.value)
        try:
            ca_cert_filename = cp.get('sslca', 'ca_cert')
            ca_key_filename = cp.get('sslca', 'ca_key')
            self.ca_key_passphrase = cp.get('sslca', 'ca_key_passphrase')
            self.cert_subject = cp.get('sslca', 'cert_subject')
            self.cert_days = cp.get('sslca', 'cert_days')
            self.pkey_bits = cp.get('sslca', 'pkey_bits')
        except:
            raise NoOptionError
        self.ca_cert = X509.load_cert(ca_cert_filename)
        self.ca_key = EVP.load_key(ca_key_filename, lambda x: self.ca_key_passphrase)
        self._newkey = False

    def get_key(self, entry, metadata):
        filename = self.hostkey+".H_%s" % metadata.hostname
        if filename in self.entries.keys():
            entry.text = self.entries[filename].data
            self.pkey = EVP.load_key_string(entry.text)
        else:
            (self.pkey, entry.text) = self.build_key(filename)
            keyfile = open(self.data + '/' +filename, 'w')
            keyfile.write(entry.text)
            keyfile.close()
            self._newkey = True

    def build_key(self, filename):
        """Generate new private key for client."""
        rsa_key = RSA.gen_key(int(self.pkey_bits), m2.RSA_F4)
        pkey = EVP.PKey()
        pkey.assign_rsa(rsa_key)
        keyfile = open(self.data + '/' +filename, 'w')
        keyfile.write(pkey.as_pem(cipher=None))
        keyfile.close()
        self._newkey = True
        return pkey, pkey.as_pem(cipher=None)

    def get_cert(self, entry, metadata):
        filename = self.hostcert + ".H_%s" % metadata.hostname
        # load prexisting cert, if any
        if filename in self.entries.keys() and self._newkey == False:
            cert = X509.load_cert_string(self.entries[filename].data)
            # check cert subjectAltNames match current aliases
            cert_aliases = cert.get_ext('subjectAltName')
            if cert_aliases:
                if metadata.aliases != [alias.lstrip('DNS:') for alias in cert_aliases.get_value().split(', ')]:
                    entry.text = self.build_cert(filename, metadata)
                    return
            entry.text = cert.as_text()+cert.as_string()
        else:
            entry.text = self.build_cert(filename, metadata)

    def get_serial(self):
        serialpath = self.data + '/serial'
        serial = 0
        if os.path.isfile(serialpath):
            serialfile = open(serialpath, 'r')
            serial = int(serialfile.read())
            serialfile.close()
        serialfile = open(serialpath, 'w')
        serial += 1
        serialfile.write(str(serial))
        serialfile.close()
        return serial           

    def build_cert(self, filename, metadata):
        req = self.make_request(self.pkey, metadata)
        serial = self.get_serial()
        cert = self.make_cert(req, serial, metadata.aliases)
        cert_out = cert.as_text()+cert.as_pem()
        certfile = open(self.data + '/' +filename, 'w')
        certfile.write(cert_out)
        certfile.close()
        cert_store = self.data + '/certstore'
        if not os.path.isdir(cert_store):
            os.mkdir(cert_store)
        storefile = open(cert_store + '/' + str(serial) + '.pem', 'w')
        storefile.write(cert_out)
        storefile.close()
        return cert_out

    def make_request(self, key, metadata):
        req = X509.Request()
        req.set_version(2)
        req.set_pubkey(key)
        name = X509.X509_Name()
        parts = [a.split('=') for a in self.cert_subject.split(',')]
        [setattr(name, k, v) for k,v in parts]
        name.CN = metadata.hostname
        req.set_subject_name(name)
        req.sign(key, 'sha1')
        return req
        
    def make_cert(self, req, serial, aliases):
        pkey = req.get_pubkey()
        if not req.verify(pkey):
            raise ValueError, 'Error verifying request'
        sub = req.get_subject()
        cert = X509.X509()
        cert.set_serial_number(serial)
        cert.set_version(2)
        cert.set_subject(sub)
        cert.set_issuer(self.ca_cert)
        cert.set_pubkey(pkey)
        notBefore = m2.x509_get_not_before(cert.x509)
        notAfter  = m2.x509_get_not_after(cert.x509)
        m2.x509_gmtime_adj(notBefore, 0)
        m2.x509_gmtime_adj(notAfter, 60*60*24*long(self.cert_days))
        exts = [
            ('basicConstraints','CA:FALSE'),
            ('subjectKeyIdentifier','hash'),
            ('authorityKeyIdentifier','keyid,issuer:always'),
            ('nsCertType','SSL Server'),
        ]
        if aliases:
            exts.append(('subjectAltName', ','.join(['DNS:'+alias for alias in aliases])))
        for ext in exts:
            cert.add_ext(X509.new_extension(ext[0],ext[1]))
        cert.sign(self.ca_key, 'sha1')
        return cert

    def HandleEvent(self, event=None):
        """Local event handler that does something...."""
        Bcfg2.Server.Plugin.DirectoryBacked.HandleEvent(self, event)

    def HandlesEntry(self, entry, _):
        """Handle entries dynamically."""
        return entry.tag == 'Path' and (entry.get('name').endswith(self.hostkey) or entry.get('name').endswith(self.hostcert))

