import gamin
import lxml.etree
import os

import Bcfg2.Server.Core
from Bcfg2.Server.Plugin import EntrySet


class es_testtype(object):
    def __init__(self, name, properties, specific):
        self.name = name
        self.properties = properties
        self.specific = specific
        self.handled = 0
        self.built = 0

    def handle_event(self, event):
        self.handled += 1

    def bind_entry(self, entry, metadata):
        entry.set('bound', '1')
        entry.set('name', self.name)
        self.built += 1


class metadata(object):
    def __init__(self, hostname):
        self.hostname = hostname
        self.groups = ['base', 'debian']

#FIXME add test_specific


class test_entry_set(object):
    def __init__(self):
        self.dirname = '/tmp/estest-%d' % os.getpid()
        os.path.isdir(self.dirname) or os.mkdir(self.dirname)
        self.metadata = metadata('testhost')
        self.es = EntrySet('template', self.dirname, None, es_testtype)
        self.e = Bcfg2.Server.Core.GaminEvent(1, 'template',
                                         gamin.GAMExists)

    def test_init(self):
        es = self.es
        e = self.e
        e.action = 'exists'
        es.handle_event(e)
        es.handle_event(e)
        assert len(es.entries) == 1
        assert list(es.entries.values())[0].handled == 2
        e.action = 'changed'
        es.handle_event(e)
        assert list(es.entries.values())[0].handled == 3

    def test_info(self):
        """Test info and info.xml handling."""
        es = self.es
        e = self.e
        dirname = self.dirname
        metadata = self.metadata

        # test 'info' handling
        assert es.metadata['group'] == 'root'
        self.mk_info(dirname)
        e.filename = 'info'
        e.action = 'exists'
        es.handle_event(e)
        assert es.metadata['group'] == 'sys'
        e.action = 'deleted'
        es.handle_event(e)
        assert es.metadata['group'] == 'root'

        # test 'info.xml' handling
        assert es.infoxml == None
        self.mk_info_xml(dirname)
        e.filename = 'info.xml'
        e.action = 'exists'
        es.handle_event(e)
        assert es.infoxml
        e.action = 'deleted'
        es.handle_event(e)
        assert es.infoxml == None

    def test_file_building(self):
        """Test file building."""
        self.test_init()
        ent = lxml.etree.Element('foo')
        self.es.bind_entry(ent, self.metadata)
        print(list(self.es.entries.values())[0])
        assert list(self.es.entries.values())[0].built == 1

    def test_host_specific_file_building(self):
        """Add a host-specific template and build it."""
        self.e.filename = 'template.H_%s' % self.metadata.hostname
        self.e.action = 'exists'
        self.es.handle_event(self.e)
        assert len(self.es.entries) == 1
        ent = lxml.etree.Element('foo')
        self.es.bind_entry(ent, self.metadata)
        # FIXME need to test that it built the _right_ file here

    def test_deletion(self):
        """Test deletion of files."""
        self.test_init()
        self.e.filename = 'template'
        self.e.action = 'deleted'
        self.es.handle_event(self.e)
        assert len(self.es.entries) == 0

    # TODO - how to clean up the temp dir & files after tests done?

    def mk_info(self, dir):
        i = open("%s/info" % dir, 'w')
        i.write('owner: root\n')
        i.write('group: sys\n')
        i.write('perms: 0600\n')
        i.close

    def mk_info_xml(self, dir):
        i = open("%s/info.xml" % dir, 'w')
        i.write('<FileInfo><Info owner="root" group="other" perms="0600" /></FileInfo>\n')
        i.close
