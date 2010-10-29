"""
Notes:

1. Put these notes in real docs!!!
2. dir structure for CA's must be correct
3. for subjectAltNames to work, openssl.conf must have copy_extensions on
"""


import Bcfg2.Server.Plugin
import lxml.etree
import posixpath
import tempfile
from subprocess import Popen, PIPE
from ConfigParser import ConfigParser

import pdb

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

    def HandleEvent(self, event=None):
        action = event.code2str()
        if event.filename[0] == '/' or event.filename.startswith('CAs'):
            return
        epath = "".join([self.data, self.handles[event.requestID],
                         event.filename])
        if posixpath.isdir(epath):
            ident = self.handles[event.requestID] + event.filename
        else:
            ident = self.handles[event.requestID][:-1]
        
        self.logger.error('ACTION: %s, IDENT %s, FILENAME %s' % (action, ident, event.filename))

        fname = "".join([ident, '/', event.filename])
        

        # TODO: check/fix handling of _all_ .xml file events vs hostfiles
        if action in ['exists', 'created']:
            if posixpath.isdir(epath):
                self.AddDirectoryMonitor(epath[len(self.data):])
            if ident not in self.entries and posixpath.isfile(epath):
                if event.filename.endswith('key.xml'):
                    key_spec = dict(lxml.etree.parse(epath).find('Key').items())
                    self.key_specs[ident] = {
                        'bits': key_spec.get('bits', 2048),
                        'type': key_spec.get('type', 'rsa')
                    }
                    self.Entries['Path'][ident] = self.get_key
                elif event.filename.endswith('cert.xml'):
                    cert_spec = dict(lxml.etree.parse(epath).find('Cert').items())
                    self.cert_specs[ident] = {
                        'ca': cert_spec.get('ca', 'default'),
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
                    self.Entries['Path'][ident] = self.get_cert
                else:
                    self.entries[fname] = self.__child__(epath)
                    self.entries[fname].HandleEvent(event)
        if action == 'changed':
            self.entries[fname].HandleEvent(event)
        elif action == 'deleted':
            if fname in self.entries:
                # a directory was deleted
                del self.entries[fname]
            else:
                self.entries[fname].HandleEvent(event)

    def get_key(self, entry, metadata):
        # set path type and permissions, otherwise bcfg2 won't bind the file
        permdata = {'owner':'root',
                    'group':'root',
                    'type':'file',
                    'perms':'644'}
        [entry.attrib.__setitem__(key, permdata[key]) for key in permdata]
        
        # check if we already have a hostfile, or need to generate a new key
        # TODO: verify key fits the specs
        path = entry.get('name')
        filename = "".join([path, '/', path.rsplit('/', 1)[1], '.H_', metadata.hostname])
        if filename not in self.entries.keys():
            key = self.build_key(filename, entry, metadata)
            open(self.data + filename, 'w').write(key)
            entry.text = key
        else:
            entry.text = self.entries[filename].data

    def build_key(self, filename, entry, metadata):
        type = self.key_specs[entry.get('name')]['type']
        bits = self.key_specs[entry.get('name')]['bits']
        if type == 'rsa':
            cmd = "openssl genrsa %s " % bits
        elif type == 'dsa':
            cmd = "openssl dsaparam -noout -genkey %s" % bits
        key = Popen(cmd, shell=True, stdout=PIPE).stdout.read()
        return key

    def get_cert(self, entry, metadata):
        # set path type and permissions, otherwise bcfg2 won't bind the file
        permdata = {'owner':'root',
                    'group':'root',
                    'type':'file',
                    'perms':'644'}
        [entry.attrib.__setitem__(key, permdata[key]) for key in permdata]

        path = entry.get('name')
        filename = "".join([path, '/', path.rsplit('/', 1)[1], '.H_', metadata.hostname])

        # first - ensure we have a key to work with
        key = self.cert_specs[entry.get('name')].get('key')
        key_filename = "".join([key, '/', key.rsplit('/', 1)[1], '.H_', metadata.hostname])
        if key_filename not in self.entries:
            e = lxml.etree.Element('Path')
            e.attrib['name'] = key
            self.core.Bind(e, metadata)

        # check if we have a valid hostfile
        if filename in self.entries.keys() and self.verify_cert():
            entry.text = self.entries[filename].data
        else:
            cert = self.build_cert(entry, metadata)
            open(self.data + filename, 'w').write(cert)
            entry.text = cert

    def verify_cert(self):
        return False

    def build_cert(self, entry, metadata):
        req_config = self.build_req_config(entry, metadata)
        req = self.build_request(req_config, entry)
        ca_config = "".join([self.data, '/CAs/', self.cert_specs[entry.get('name')]['ca'], '/', 'openssl.cnf'])
        days = self.cert_specs[entry.get('name')]['days']
        cmd = "openssl ca -config %s -in %s -days %s -batch -passin pass:TODO!!!!" % (ca_config, req, days)
        pdb.set_trace()
        cert = Popen(cmd, shell=True, stdout=PIPE).stdout.read()
        # TODO: remove tempfiles
        return cert

    def build_req_config(self, entry, metadata):
        # create temp request config file
        conffile = open(tempfile.mkstemp()[1], 'w')
        cp = ConfigParser({})
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
        for section in defaults.keys():
            cp.add_section(section)
            for key in defaults[section]:
                cp.set(section, key, defaults[section][key])
        x = 1
        for alias in metadata.aliases:
            cp.set('alt_names', 'DNS.'+str(x), alias)
            x += 1
        for item in ['C', 'L', 'ST', 'O', 'OU', 'emailAddress']:
            if self.cert_specs[entry.get('name')][item]:
                cp.set('req_distinguished_name', item, self.cert_specs[entry.get('name')][item])
        cp.set('req_distinguished_name', 'CN', metadata.hostname)
        cp.write(conffile)
        conffile.close()
        return conffile.name
        
    def build_request(self, req_config, entry):
        req = tempfile.mkstemp()[1]
        key = self.cert_specs[entry.get('name')]['key']
        days = self.cert_specs[entry.get('name')]['days']
        cmd = "openssl req -new -config %s -days %s -key %s -text -out %s" % (req_config, days, key, req)
        res = Popen(cmd, shell=True, stdout=PIPE).stdout.read()
        return req

