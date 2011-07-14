import os.path
import lxml.etree
import Bcfg2.Server.Lint

class RequiredAttrs(Bcfg2.Server.Lint.ServerPlugin):
    """ verify attributes for configuration entries (as defined in
    doc/server/configurationentries) """

    def __init__(self, *args, **kwargs):
        Bcfg2.Server.Lint.ServerPlugin.__init__(self, *args, **kwargs)
        self.required_attrs = {
            'device': ['name', 'owner', 'group', 'dev_type'],
            'directory': ['name', 'owner', 'group', 'perms'],
            'file': ['name', 'owner', 'group', 'perms'],
            'hardlink': ['name', 'to'],
            'symlink': ['name', 'to'],
            'ignore': ['name'],
            'nonexistent': ['name'],
            'permissions': ['name', 'owner', 'group', 'perms']}

    def Run(self):
        self.check_rules()
        self.check_bundles()

    def check_rules(self):
        """ check Rules for Path entries with missing attrs """
        if 'Rules' in self.core.plugins:
            for rules in self.core.plugins['Rules'].entries.values():
                xdata = rules.pnode.data
                for path in xdata.xpath("//Path"):
                    self.check_entry(path, os.path.join(self.config['repo'],
                                                        rules.name))

    def check_bundles(self):
        """ check bundles for BoundPath entries with missing attrs """
        if 'Bundler' in self.core.plugins:
            for bundle in self.core.plugins['Bundler'].entries.values():
                try:
                    xdata = lxml.etree.XML(bundle.data)
                except AttributeError:
                    xdata = lxml.etree.parse(bundle.template.filepath).getroot()

                for path in xdata.xpath("//BoundPath"):
                    self.check_entry(path, bundle.name)

    def check_entry(self, entry, filename):
        """ generic entry check """
        if self.HandlesFile(filename):
            pathname = entry.get('name')
            pathtype = entry.get('type')
            pathset = set(entry.attrib.keys())
            try:
                required_attrs = set(self.required_attrs[pathtype] + ['type'])
            except KeyError:
                self.LintError("unknown-path-type",
                               "Unknown path type %s: %s" %
                               (pathtype, self.RenderXML(entry)))

            if 'dev_type' in required_attrs:
                dev_type = entry.get('dev_type')
                if dev_type in ['block', 'char']:
                    # check if major/minor are specified
                    required_attrs |= set(['major', 'minor'])
            if not pathset.issuperset(required_attrs):
                self.LintError("required-attrs-missing",
                               "The required attributes %s are missing for %s %sin %s:\n%s" %
                               (",".join([attr
                                          for attr in
                                          required_attrs.difference(pathset)]),
                                entry.tag, pathname, filename,
                                self.RenderXML(entry)))
