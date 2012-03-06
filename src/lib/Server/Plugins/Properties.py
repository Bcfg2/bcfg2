import os
import re
import sys
import copy
import logging
import lxml.etree
from Bcfg2.metargs import Option
import Bcfg2.Server.Plugin
import Bcfg2.Options

logger = logging.getLogger('Bcfg2.Plugins.Properties')

class Fake(object):
    """
    An object that pretends to be an lxml etree node, but that has no children, fake text, and
    that duplicates itself when any attribute is retrieved or when it is called
    """
    def __init__(self, name):
        self.name = name

    def __getattr__(self, name):
        if name == 'text':
            return str(self)
        else:
            return Fake('.'.join([self.name, name]))

    def __call__(self, *args, **kwargs):
        return Fake('%s(args=%s, kwargs=%s)' % (self.name, args, kwargs))

    def __str__(self):
        return "FAKE: " + self.name

    def __iter__(self):
        if False:
            yield None
        return
    
    def __getitem__(self, key):
        return Fake('%s[%s]' % (self.name, key))

    def __len__(self):
        return 0

class MissingPropertyException(Exception):
    """
    Thrown if a property doesn't exist at the path in the file
    """
    def __init__(self, filename, path):
        Exception.__init__(
            self,
            "No property found in file '%s' at path '%s'" % (filename, path)
        )

class MalformedPropertiesFileException(Exception):
    """
    Thrown if a property file is probably malformed
    """
    def __init__(self, filename, path):
        Exception.__init__(
            self,
            "Properties file '%s' is probably malformed. Discovered while reading property '%s'" % (filename, path)
        )

class MissingFileException(Exception):
    """
    Thrown if a properties file doesn't exist
    """
    def __init__(self, filename):
        Exception.__init__(
            self,
            "No properties file '%s'" % filename
        )

class UnexpectedChildrenException(Exception):
    """
    Thrown if there are children in a property that we were expecting to have only a value
    """
    def __init__(self, filename, path):
        Exception.__init__(
            self,
            "Expected a single valued property in file '%s' at path '%s', but found a node with children instead" % (filename, path)
        )

class PropertyFile(Bcfg2.Server.Plugin.StructFile):
    """Class for properties files."""
    def write(self):
        """ Write the data in this data structure back to the property
        file """
        if self.validate_data():
            try:
                open(self.name,
                     "wb").write(lxml.etree.tostring(self.xdata,
                                                     pretty_print=True))
                return True
            except IOError:
                err = sys.exc_info()[1]
                logger.error("Failed to write %s: %s" % (self.name, err))
                return False
        else:
            return False

    def validate_data(self):
        """ ensure that the data in this object validates against the
        XML schema for this property file (if a schema exists) """
        schemafile = self.name.replace(".xml", ".xsd")
        if os.path.exists(schemafile):
            try:
                schema = lxml.etree.XMLSchema(file=schemafile)
            except:
                logger.error("Failed to process schema for %s" % self.name)
                return False
        else:
            # no schema exists
            return True

        if not schema.validate(self.xdata):
            logger.error("Data for %s fails to validate; run bcfg2-lint for "
                         "more details" % self.name)
            return False
        else:
            return True


class PropDirectoryBacked(Bcfg2.Server.Plugin.DirectoryBacked):
    __child__ = PropertyFile
    patterns = re.compile(r'.*\.xml$')


class Properties(Bcfg2.Server.Plugin.Plugin,
                 Bcfg2.Server.Plugin.Connector):
    """
       The properties plugin maps property
       files into client metadata instances.
    """
    name = 'Properties'
    version = '$Revision$'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        try:
            self.store = PropDirectoryBacked(self.data, core.fam)
        except OSError:
            e = sys.exc_info()[1]
            self.logger.error("Error while creating Properties store: %s %s" %
                              (e.strerror, e.filename))
            raise Bcfg2.Server.Plugin.PluginInitError
        self.default_property_files = Bcfg2.Options.bootstrap().default_property_files

    @classmethod
    def register_options(cls, args=None):
        Bcfg2.Options.add_options(
            Option('--default-property-files', 'testing:default_property_files',
                nargs='+', default=[], dest='default_property_files', metavar='file',
                help="Property files to mock out if they don't exist in the repository")
        )

    def get_additional_data(self, _):
        return PropertyQuery(self.store.entries)

class PropertyQuery(dict):

    def find_property(self, filename, path):
        '''
        Return the lxml node in filename found at the specified path.
        Throws a MissingPropertyException if there is no node at the specified path.
        '''
        if filename not in self.keys():
            if filename in self.default_property_files:
                return Fake(':'.join([filename, path]))
            else:
                raise MissingFileException(filename)

        node = self[filename].xdata.find(path)
        if node is None:
            raise MissingPropertyException(filename, path)

        if node == -1:
            raise MalformedPropertiesFileException(filename, path)

        return node

    def find_value(self, filename, path):
        '''
        Return the value of the node of the specified path from the properties file with the specified name.
        Throws a MissingPropertyException if there is no node at the specified path
        Throws a UnexpectedChildrenException if the node does not have a single text value inside it
        '''
        node = self.find_property(filename, path)

        if len(node) > 0:
            raise UnexpectedChildrenException(filename, path)
        return node.text

    def find_children(self, filename, path, child_node):
        '''
        @return a list of child nodes of the node of the specified path from the properties file with the specified name.
        @throws a MissingPropertyException if there is no node at the specified path.
        '''
        node = self.find_property(filename, path)

        for n in node.findall(child_node):
            yield n

    def find_matching_values_list(self, filename, path, value_name):
        '''
        @return a list of the texts of the child values of the node of the specified path from the properties file with the specified name.
        @throws a MissingPropertyException if there is no node at the specified path.
        '''
        for node in self.find_children(filename, path, value_name):
            yield node.text
