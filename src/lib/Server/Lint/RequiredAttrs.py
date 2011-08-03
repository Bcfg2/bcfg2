import os.path
import lxml.etree
import Bcfg2.Server.Lint
import Bcfg2.Server.Plugins.Packages

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
            'permissions': ['name', 'owner', 'group', 'perms'],
            'vcs': ['vcstype', 'revision', 'sourceurl']}

    def Run(self):
        self.check_rules()
        self.check_bundles()
        self.check_packages()

    def check_packages(self):
        """ check package sources for Source entries with missing attrs """
        if 'Packages' in self.core.plugins:
            for source in self.core.plugins['Packages'].sources:
                if isinstance(source, Bcfg2.Server.Plugin.Packages.PulpSource):
                    if not source.id:
                        self.LintError("required-attrs-missing",
                                       "The required attribute id is missing "
                                       "from a Pulp source: %s" %
                                       self.RenderXML(source.xsource))
                else:
                    if not source.url and not source.rawurl:
                        self.LintError("required-attrs-missing",
                                       "A %s source must have either a url or "
                                       "rawurl attribute: %s" %
                                       (source.ptype,
                                        self.RenderXML(source.xsource)))

                if (not isinstance(source,
                                   Bcfg2.Server.Plugin.Packages.APTSource) and
                    source.recommended):
                    self.LintError("extra-attrs",
                                   "The recommended attribute is not "
                                   "supported on %s sources: %s" %
                                   (source.ptype,
                                    self.RenderXML(source.xsource)))

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
                return

            if 'dev_type' in required_attrs:
                dev_type = entry.get('dev_type')
                if dev_type in ['block', 'char']:
                    # check if major/minor are specified
                    required_attrs |= set(['major', 'minor'])

            if pathtype == 'file' and not entry.text:
                self.LintError("required-attrs-missing",
                               "Text missing for %s %s in %s: %s" %
                               (entry.tag, pathname, filename,
                                self.RenderXML(entry)))

            if not pathset.issuperset(required_attrs):
                self.LintError("required-attrs-missing",
                               "The required attributes %s are missing for %s %sin %s:\n%s" %
                               (",".join([attr
                                          for attr in
                                          required_attrs.difference(pathset)]),
                                entry.tag, pathname, filename,
                                self.RenderXML(entry)))
