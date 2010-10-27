import Bcfg2.Server.Plugin
from subprocess import Popen, PIPE
import lxml.etree
import posixpath
import logging
import pdb

class SSLCA(Bcfg2.Server.Plugin.GroupSpool):
            #Bcfg2.Server.Plugin.Plugin,
            #Bcfg2.Server.Plugin.Generator,
            #Bcfg2.Server.Plugin.DirectoryBacked):

    """
    The SSLCA generator handles the creation and
    management of ssl certificates and their keys.
    """
    name = 'SSLCA'
    __version__ = '$Id:$'
    __author__ = 'g.hagger@gmail.com'
    __child__ = Bcfg2.Server.Plugin.FileBacked

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.GroupSpool.__init__(self, core, datastore)
#        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
#        Bcfg2.Server.Plugin.Generator.__init__(self)
#        try:
#            Bcfg2.Server.Plugin.DirectoryBacked.__init__(self, self.data,
#                                                         self.core.fam)
#        except OSError, ioerr:
#            self.logger.error("Failed to load SSHbase repository from %s" \
#                              % (self.data))
#            self.logger.error(ioerr)
#            raise Bcfg2.Server.Plugin.PluginInitError
#
    def HandleEvent(self, event=None):
        action = event.code2str()
        if event.filename[0] == '/':
            return
        epath = "".join([self.data, self.handles[event.requestID],
                         event.filename])
        if posixpath.isdir(epath):
            ident = self.handles[event.requestID] + event.filename
        else:
            ident = self.handles[event.requestID][:-1]
        
        self.logger.error('ACTION: %s, IDENT %s, FILENAME %s' % (action, ident, event.filename))

        if action in ['exists', 'created']:
            if posixpath.isdir(epath):
                self.AddDirectoryMonitor(epath[len(self.data):])
            if ident not in self.entries and posixpath.isfile(epath):
                if event.filename.endswith('key.xml'):
                    self.Entries['Path'][ident] = self.get_key
                elif event.filename.endswith('cert.xml'):
                    pass
#                    self.Entries['Path'][ident] = self.get_cert
                else:
                    fname = "".join([ident, '/', event.filename])
                    self.entries[fname] = self.__child__(epath)
                    self.entries[fname].HandleEvent(event)
        if action == 'changed':
            self.entries[ident].HandleEvent(event)
        elif action == 'deleted':
            fbase = self.handles[event.requestID] + event.filename
            if fbase in self.entries:
                # a directory was deleted
                del self.entries[fbase]
                del self.Entries['Path'][fbase]
            else:
                self.entries[ident].HandleEvent(event)

    def get_key(self, entry, metadata):
        path = entry.get('name')
        permdata = {'owner':'root',
                    'group':'root',
                    'type':'file',
                    'perms':'644'}
        [entry.attrib.__setitem__(key, permdata[key]) for key in permdata]
        filename = "".join([path, '/', path.rsplit('/', 1)[1], '.H_', metadata.hostname])
        if filename not in self.entries.keys():
            key = self.build_key(filename, metadata)
            open(self.data + filename, 'w').write(key)
            entry.text = key
        else:
            entry.text = self.entries[filename].data

    def build_key(self, filename, metadata):
        # TODO read params
        type = 'rsa'
        bits = 2048
        if type == 'rsa':
            cmd = "openssl genrsa %s " % bits
        elif type == 'dsa':
            cmd = "openssl dsaparam -noout -genkey %s" % bits
        key = Popen(cmd, shell=True, stdout=PIPE).stdout.read()
        return key

    def get_cert(self, entry, metadata):
        path = entry.get('name')
        permdata = {'owner':'root',
                    'group':'root',
                    'type':'file',
                    'perms':'644'}
        [entry.attrib.__setitem__(key, permdata[key]) for key in permdata]
        filename = "".join([path, '/', path.rsplit('/', 1)[1], '.H_', metadata.hostname])
        if filename in self.entries.keys() and self.verify_cert(filename) :
            entry.text = self.entries[filename].data
        else:
            cert = self.build_cert(filename, metadata)
            open(self.data + filename, 'w').write(cert)
            entry.text = cert

    def verify_cert(self):
        # TODO
        # check cert matches key
        # check expiry
        pass

    def build_req(self):
        pass

    def build_cert(self):
        pass









































#class SSLCAFile:
#
#    def __init__(self, datastore, name, specific, encoding):
#        self.data = datastore
#        self.name = name
#        self.specific = specific
#        self.encoding = encoding
#        if name.endswith('.xml'):
#            self.xml = lxml.etree.parse(name)
#
#    def handle_event(self, event=None):
#        """Handle all fs events for this file."""
#        if event and event.code2str() == 'deleted':
#            return
#
#    def bind_entry(self, entry, metadata):
#        pdb.set_trace()
#
#
#class SSLCAKeyFile(SSLCAFile):
#
#    def __init__(self, datastore, name, specific, encoding):
#        SSLCAFile.__init__(self, datastore, name, specific, encoding)
#        key_attrs = self.xml.find('Key')
#        self.bits = key_attrs.get('bits')
#        self.type = key_attrs.get('type')
#
#    def bind_entry(self, entry, metadata):
#        """Build literal file information."""
#        if entry.tag == 'Path':
#            entry.set('type', 'file')
#        entry.text = self.get_key(entry, metadata)
#
#    def get_key(self, entry, metadata):
#        fname =  +dir '.H_' + metadata.hostname
#        # TODO add logic to get+verify key if hostfile exists & save if not
#        pdb.set_trace()
#        return self.build_key()
#
#    def build_key(self):
#        if self.type == 'rsa':
#            cmd = "openssl genrsa %s " % self.bits
#        elif self.type == 'dsa':
#            cmd = "openssl dsaparam -noout -genkey %s" % self.bits
#        key = Popen(cmd, shell=True, stdout=PIPE).stdout.read()
#        return key
#
#
#class SSLCACertFile(SSLCAFile):
#
#    def __init__(self, datastore, name, specific, encoding):
#        SSLCAFile.__init__(self, datastore, name, specific, encoding)
#        cert_attrs = self.xml.find('Cert')
#        #self.format = cert_attrs.get('format')
#        #self.key = cert_attrs.get('key')
#        #self.ca = cert_attrs.get('ca')
#
#    def bind_entry(self, entry, metadata):
#        """Build literal file information."""
#        fname = entry.get('realname', entry.get('name'))
#        if entry.tag == 'Path':
#            entry.set('type', 'file')
#        entry.text = 'booya cert'
#
#
#class SSLCAEntrySet(Bcfg2.Server.Plugin.EntrySet):
#    """
#    Handles host and group specific entries
#    """
#    def __init__(self, datastore, basename, path, entry_type, encoding):
#        self.data = datastore
#        Bcfg2.Server.Plugin.EntrySet.__init__(self, basename, path, entry_type, encoding)
#
#    def entry_init(self, event):
#        """Handle template and info file creation."""
#        logger = logging.getLogger('Bcfg2.Plugins.SSLCA')
#        if event.filename in self.entries:
#            logger.warn("Got duplicate add for %s" % event.filename)
#        else:
#            fpath = "%s/%s" % (self.path, event.filename)
#            try:
#                spec = self.specificity_from_filename(event.filename)
#            except Bcfg2.Server.Plugin.SpecificityError:
#                if not self.ignore.match(event.filename):
#                    logger.error("Could not process filename %s; ignoring" % fpath)
#                return
#            self.entries[event.filename] = self.entry_type(self.data, fpath,
#                                                           spec, self.encoding)
#        self.entries[event.filename].handle_event(event)
#
#
#class SSLCA(Bcfg2.Server.Plugin.GroupSpool):
#    """
#    The SSLCA generator handles the creation and
#    management of ssl certificates and their keys.
#    """
#    name = 'SSLCA'
#    __version__ = '$Id:$'
#    __author__ = 'g.hagger@gmail.com'
#    filename_pattern = '(key|cert)\.xml'
#    es_cls = SSLCAEntrySet
#
#    def __init__(self, core, datastore):
#        Bcfg2.Server.Plugin.GroupSpool.__init__(self, core, datastore)
#
#    def HandleEvent(self, event):
#        action = event.code2str()
#        if event.filename[0] == '/':
#            return
#        epath = "".join([self.data, self.handles[event.requestID],
#                         event.filename])
#        if posixpath.isdir(epath):
#            ident = self.handles[event.requestID] + event.filename
#        else:
#            ident = self.handles[event.requestID][:-1]
#
#        if action in ['exists', 'created']:
#            if posixpath.isdir(epath):
#                self.AddDirectoryMonitor(epath[len(self.data):])
#            if ident not in self.entries and posixpath.isfile(epath):
#                if event.filename.endswith('key.xml'):
#                    es_child_cls = SSLCAKeyFile
#                elif event.filename.endswith('cert.xml'):
#                    es_child_cls = SSLCACertFile
#                else:
#                    return
#                dirpath = "".join([self.data, ident])
#                self.entries[ident] = self.es_cls(self.data,
#                                                  self.filename_pattern,
#                                                  dirpath,
#                                                  es_child_cls,
#                                                  self.encoding)
#                self.Entries['Path'][ident] = self.entries[ident].bind_entry
#            if not posixpath.isdir(epath):
#                # do not pass through directory events
#                self.entries[ident].handle_event(event)
#        if action == 'changed':
#            self.entries[ident].handle_event(event)
#        elif action == 'deleted':
#            fbase = self.handles[event.requestID] + event.filename
#            if fbase in self.entries:
#                # a directory was deleted
#                del self.entries[fbase]
#                del self.Entries['Path'][fbase]
#            else:
#                self.entries[ident].handle_event(event)










#import Bcfg2.Options
#import os
#from ConfigParser import ConfigParser, NoSectionError, NoOptionError
#from M2Crypto import RSA, EVP, X509, m2

#class SSLCA(Bcfg2.Server.Plugin.Plugin,
#              Bcfg2.Server.Plugin.Generator,
#              Bcfg2.Server.Plugin.DirectoryBacked):
#    """
#        The sslca generator manages ssl certificates
#        and keys
#    """
#
#    name = 'SSLbase'
#    __version__ = '0.00000000001'
#    __author__ = 'ghagger@wgen.net'
#
#    hostkey = 'localhost.key'
#    hostcert = 'localhost.crt'
#
#    def __init__(self, core, datastore):
#        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
#        Bcfg2.Server.Plugin.Generator.__init__(self)
#        try:
#            Bcfg2.Server.Plugin.DirectoryBacked.__init__(self, self.data,
#                                                         self.core.fam)
#        except OSError, ioerr:
#            self.logger.error("Failed to load SSLbase repository from %s" \
#                              % (self.data))
#            self.logger.error(ioerr)
#            raise Bcfg2.Server.Plugin.PluginInitError
#        self.Entries = {'Path':
#                        {'/etc/pki/tls/private/localhost.key': self.get_key,
#                         '/etc/pki/tls/certs/localhost.crt': self.get_cert}}
#        # grab essential sslca configuration from bcfg2.conf
#        cp = ConfigParser()
#        cp.read(Bcfg2.Options.CFILE.value)
#        try:
#            ca_cert_filename = cp.get('sslca', 'ca_cert')
#            ca_key_filename = cp.get('sslca', 'ca_key')
#            self.ca_key_passphrase = cp.get('sslca', 'ca_key_passphrase')
#            self.cert_subject = cp.get('sslca', 'cert_subject')
#            self.cert_days = cp.get('sslca', 'cert_days')
#            self.pkey_bits = cp.get('sslca', 'pkey_bits')
#        except:
#            raise NoOptionError
#        self.ca_cert = X509.load_cert(ca_cert_filename)
#        self.ca_key = EVP.load_key(ca_key_filename, lambda x: self.ca_key_passphrase)
#        self._newkey = False
#
#    def get_key(self, entry, metadata):
#        filename = self.hostkey+".H_%s" % metadata.hostname
#        if filename in self.entries.keys():
#            entry.text = self.entries[filename].data
#            self.pkey = EVP.load_key_string(entry.text)
#        else:
#            (self.pkey, entry.text) = self.build_key(filename)
#            keyfile = open(self.data + '/' +filename, 'w')
#            keyfile.write(entry.text)
#            keyfile.close()
#            self._newkey = True
#
#    def build_key(self, filename):
#        """Generate new private key for client."""
#        rsa_key = RSA.gen_key(int(self.pkey_bits), m2.RSA_F4)
#        pkey = EVP.PKey()
#        pkey.assign_rsa(rsa_key)
#        keyfile = open(self.data + '/' +filename, 'w')
#        keyfile.write(pkey.as_pem(cipher=None))
#        keyfile.close()
#        self._newkey = True
#        return pkey, pkey.as_pem(cipher=None)
#
#    def get_cert(self, entry, metadata):
#        filename = self.hostcert + ".H_%s" % metadata.hostname
#        # load prexisting cert, if any
#        if filename in self.entries.keys() and self._newkey == False:
#            cert = X509.load_cert_string(self.entries[filename].data)
#            # check cert subjectAltNames match current aliases
#            cert_aliases = cert.get_ext('subjectAltName')
#            if cert_aliases:
#                if metadata.aliases != [alias.lstrip('DNS:') for alias in cert_aliases.get_value().split(', ')]:
#                    entry.text = self.build_cert(filename, metadata)
#                    return
#            entry.text = cert.as_text()+cert.as_string()
#        else:
#            entry.text = self.build_cert(filename, metadata)
#
#    def get_serial(self):
#        serialpath = self.data + '/serial'
#        serial = 0
#        if os.path.isfile(serialpath):
#            serialfile = open(serialpath, 'r')
#            serial = int(serialfile.read())
#            serialfile.close()
#        serialfile = open(serialpath, 'w')
#        serial += 1
#        serialfile.write(str(serial))
#        serialfile.close()
#        return serial           
#
#    def build_cert(self, filename, metadata):
#        req = self.make_request(self.pkey, metadata)
#        serial = self.get_serial()
#        cert = self.make_cert(req, serial, metadata.aliases)
#        cert_out = cert.as_text()+cert.as_pem()
#        certfile = open(self.data + '/' +filename, 'w')
#        certfile.write(cert_out)
#        certfile.close()
#        cert_store = self.data + '/certstore'
#        if not os.path.isdir(cert_store):
#            os.mkdir(cert_store)
#        storefile = open(cert_store + '/' + str(serial) + '.pem', 'w')
#        storefile.write(cert_out)
#        storefile.close()
#        return cert_out
#
#    def make_request(self, key, metadata):
#        req = X509.Request()
#        req.set_version(2)
#        req.set_pubkey(key)
#        name = X509.X509_Name()
#        parts = [a.split('=') for a in self.cert_subject.split(',')]
#        [setattr(name, k, v) for k,v in parts]
#        name.CN = metadata.hostname
#        req.set_subject_name(name)
#        req.sign(key, 'sha1')
#        return req
#        
#    def make_cert(self, req, serial, aliases):
#        pkey = req.get_pubkey()
#        if not req.verify(pkey):
#            raise ValueError, 'Error verifying request'
#        sub = req.get_subject()
#        cert = X509.X509()
#        cert.set_serial_number(serial)
#        cert.set_version(2)
#        cert.set_subject(sub)
#        cert.set_issuer(self.ca_cert)
#        cert.set_pubkey(pkey)
#        notBefore = m2.x509_get_not_before(cert.x509)
#        notAfter  = m2.x509_get_not_after(cert.x509)
#        m2.x509_gmtime_adj(notBefore, 0)
#        m2.x509_gmtime_adj(notAfter, 60*60*24*long(self.cert_days))
#        exts = [
#            ('basicConstraints','CA:FALSE'),
#            ('subjectKeyIdentifier','hash'),
#            ('authorityKeyIdentifier','keyid,issuer:always'),
#            ('nsCertType','SSL Server'),
#        ]
#        if aliases:
#            exts.append(('subjectAltName', ','.join(['DNS:'+alias for alias in aliases])))
#        for ext in exts:
#            cert.add_ext(X509.new_extension(ext[0],ext[1]))
#        cert.sign(self.ca_key, 'sha1')
#        return cert
#
#    def HandleEvent(self, event=None):
#        """Local event handler that does something...."""
#        Bcfg2.Server.Plugin.DirectoryBacked.HandleEvent(self, event)
#
#    def HandlesEntry(self, entry, _):
#        """Handle entries dynamically."""
#        return entry.tag == 'Path' and (entry.get('name').endswith(self.hostkey) or entry.get('name').endswith(self.hostcert))
#
