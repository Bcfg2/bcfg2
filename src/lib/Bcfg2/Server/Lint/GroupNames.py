import os
import re
import Bcfg2.Server.Lint
try:
    from Bcfg2.Server.Plugins.Bundler import BundleTemplateFile
    has_genshi = True
except ImportError:
    has_genshi = False

class GroupNames(Bcfg2.Server.Lint.ServerPlugin):
    """ ensure that all named groups are valid group names """
    pattern = r'\S+$'
    valid = re.compile(r'^' + pattern)

    def Run(self):
        self.check_metadata()
        if 'Rules' in self.core.plugins:
            self.check_rules()
        if 'Bundler' in self.core.plugins:
            self.check_bundles()
        if 'GroupPatterns' in self.core.plugins:
            self.check_grouppatterns()
        if 'Cfg' in self.core.plugins:
            self.check_cfg()

    @classmethod
    def Errors(cls):
        return {"invalid-group-name": "error"}

    def check_rules(self):
        for rules in self.core.plugins['Rules'].entries.values():
            if not self.HandlesFile(rules.name):
                continue
            xdata = rules.pnode.data
            self.check_entries(xdata.xpath("//Group"),
                               os.path.join(self.config['repo'], rules.name))

    def check_bundles(self):
        """ check bundles for BoundPath entries with missing attrs """
        for bundle in self.core.plugins['Bundler'].entries.values():
            if (self.HandlesFile(bundle.name) and
                (not has_genshi or
                 not isinstance(bundle, BundleTemplateFile))):
                self.check_entries(bundle.xdata.xpath("//Group"),
                                   bundle.name)

    def check_metadata(self):
        self.check_entries(self.metadata.groups_xml.xdata.xpath("//Group"),
                           os.path.join(self.config['repo'],
                                        self.metadata.groups_xml.name))

    def check_grouppatterns(self):
        cfg = self.core.plugins['GroupPatterns'].config
        if not self.HandlesFile(cfg.name):
            return
        for grp in cfg.xdata.xpath('//GroupPattern/Group'):
            if not self.valid.search(grp.text):
                self.LintError("invalid-group-name",
                               "Invalid group name in %s: %s" %
                               (cfg.name, self.RenderXML(grp, keep_text=True)))

    def check_cfg(self):
        for root, dirs, files in os.walk(self.core.plugins['Cfg'].data):
            for fname in files:
                basename = os.path.basename(root)
                if (re.search(r'^%s\.G\d\d_' % basename, fname) and
                    not re.search(r'^%s\.G\d\d_' % basename + self.pattern,
                                  fname)):
                    self.LintError("invalid-group-name",
                                   "Invalid group name referenced in %s" %
                                   os.path.join(root, fname))

    def check_entries(self, entries, fname):
        for grp in entries:
            if not self.valid.search(grp.get("name")):
                self.LintError("invalid-group-name",
                               "Invalid group name in %s: %s" %
                               (fname, self.RenderXML(grp)))
