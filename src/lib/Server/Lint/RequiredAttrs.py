import os.path
import lxml.etree
import Bcfg2.Server.Lint
from Bcfg2.Server.Plugins.Packages import Apt, Yum

class RequiredAttrs(Bcfg2.Server.Lint.ServerPlugin):
    """ verify attributes for configuration entries (as defined in
    doc/server/configurationentries) """

    def __init__(self, *args, **kwargs):
        Bcfg2.Server.Lint.ServerPlugin.__init__(self, *args, **kwargs)
        self.required_attrs = {
            'Path': {
                'device': ['name', 'owner', 'group', 'dev_type'],
                'directory': ['name', 'owner', 'group', 'perms'],
                'file': ['name', 'owner', 'group', 'perms', '__text__'],
                'hardlink': ['name', 'to'],
                'symlink': ['name', 'to'],
                'ignore': ['name'],
                'nonexistent': ['name'],
                'permissions': ['name', 'owner', 'group', 'perms'],
                'vcs': ['vcstype', 'revision', 'sourceurl']},
            'Service': {
                'chkconfig': ['name'],
                'deb': ['name'],
                'rc-update': ['name'],
                'smf': ['name', 'FMRI'],
                'upstart': ['name']},
            'Action': ['name', 'timing', 'when', 'status', 'command'],
            'Package': ['name']}

    def Run(self):
        self.check_packages()
        if "Defaults" in self.core.plugins:
            self.logger.info("Defaults plugin enabled; skipping required "
                             "attribute checks")
        else:
            self.check_rules()
            self.check_bundles()

    def check_packages(self):
        """ check package sources for Source entries with missing attrs """
        if 'Packages' in self.core.plugins:
            for source in self.core.plugins['Packages'].sources:
                if isinstance(source, Yum.YumSource):
                    if (not source.pulp_id and not source.url and
                        not source.rawurl):
                        self.LintError("required-attrs-missing",
                                       "A %s source must have either a url, "
                                       "rawurl, or pulp_id attribute: %s" %
                                       (source.ptype,
                                        self.RenderXML(source.xsource)))
                elif not source.url and not source.rawurl:
                    self.LintError("required-attrs-missing",
                                   "A %s source must have either a url or "
                                   "rawurl attribute: %s" %
                                   (source.ptype,
                                    self.RenderXML(source.xsource)))

                if (not isinstance(source, Apt.AptSource) and
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
                except (lxml.etree.XMLSyntaxError, AttributeError):
                    xdata = lxml.etree.parse(bundle.template.filepath).getroot()

                for path in xdata.xpath("//*[substring(name(), 1, 5) = 'Bound']"):
                    self.check_entry(path, bundle.name)

    def check_entry(self, entry, filename):
        """ generic entry check """
        if self.HandlesFile(filename):
            name = entry.get('name')
            tag = entry.tag
            if tag.startswith("Bound"):
                tag = tag[5:]
            if tag not in self.required_attrs:
                self.LintError("unknown-entry-tag",
                               "Unknown entry tag '%s': %s" %
                               (entry.tag, self.RenderXML(entry)))

            if isinstance(self.required_attrs[tag], dict):
                etype = entry.get('type')
                if etype in self.required_attrs[tag]:
                    required_attrs = set(self.required_attrs[tag][etype] +
                                         ['type'])
                else:
                    self.LintError("unknown-entry-type",
                                   "Unknown %s type %s: %s" %
                                   (tag, etype, self.RenderXML(entry)))
                    return
            else:
                required_attrs = set(self.required_attrs[tag])
            attrs = set(entry.attrib.keys())

            if 'dev_type' in required_attrs:
                dev_type = entry.get('dev_type')
                if dev_type in ['block', 'char']:
                    # check if major/minor are specified
                    required_attrs |= set(['major', 'minor'])

            if '__text__' in required_attrs:
                required_attrs.remove('__text__')
                if (not entry.text and
                    not entry.get('empty', 'false').lower() == 'true'):
                    self.LintError("required-attrs-missing",
                                   "Text missing for %s %s in %s: %s" %
                                   (entry.tag, name, filename,
                                    self.RenderXML(entry)))

            if not attrs.issuperset(required_attrs):
                self.LintError("required-attrs-missing",
                               "The following required attribute(s) are "
                               "missing for %s %s in %s: %s\n%s" %
                               (entry.tag, name, filename,
                                ", ".join([attr
                                           for attr in
                                           required_attrs.difference(attrs)]),
                                self.RenderXML(entry)))
