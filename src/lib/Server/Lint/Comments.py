import os.path
import lxml.etree
import Bcfg2.Server.Lint

class Comments(Bcfg2.Server.Lint.ServerPlugin):
    """ check files for various required headers """
    def __init__(self, *args, **kwargs):
        Bcfg2.Server.Lint.ServerPlugin.__init__(self, *args, **kwargs)
        self.config_cache = {}

    def Run(self):
        self.check_bundles()
        self.check_properties()
        self.check_metadata()
        self.check_cfg()
        self.check_infoxml()
        self.check_probes()

    def required_keywords(self, rtype):
        """ given a file type, fetch the list of required VCS keywords
        from the bcfg2-lint config """
        return self.required_items(rtype, "keyword")

    def required_comments(self, rtype):
        """ given a file type, fetch the list of required comments
        from the bcfg2-lint config """
        return self.required_items(rtype, "comment")

    def required_items(self, rtype, itype):
        """ given a file type and item type (comment or keyword),
        fetch the list of required items from the bcfg2-lint config """
        if itype not in self.config_cache:
            self.config_cache[itype] = {}
            
        if rtype not in self.config_cache[itype]:
            rv = []
            global_item = "global_%ss" % itype
            if global_item in self.config:
                rv.extend(self.config[global_item].split(","))
            
            item = "%s_%ss" % (rtype.lower(), itype)
            if item in self.config:
                if self.config[item]:
                    rv.extend(self.config[item].split(","))
                else:
                    # config explicitly specifies nothing
                    rv = []
            self.config_cache[itype][rtype] = rv
        return self.config_cache[itype][rtype]

    def check_bundles(self):
        """ check bundle files for required headers """
        if 'Bundler' in self.core.plugins:
            for bundle in self.core.plugins['Bundler'].entries.values():
                xdata = None
                rtype = ""
                try:
                    xdata = lxml.etree.XML(bundle.data)
                    rtype = "bundler"
                except (lxml.etree.XMLSyntaxError, AttributeError):
                    xdata = lxml.etree.parse(bundle.template.filepath).getroot()
                    rtype = "sgenshi"

                self.check_xml(bundle.name, xdata, rtype)

    def check_properties(self):
        """ check properties files for required headers """
        if 'Properties' in self.core.plugins:
            props = self.core.plugins['Properties']
            for propfile, pdata in props.store.entries.items():
                if os.path.splitext(propfile)[1] == ".xml":
                    self.check_xml(pdata.name, pdata.xdata, 'properties')

    def check_metadata(self):
        """ check metadata files for required headers """
        if self.has_all_xincludes("groups.xml"):
            self.check_xml(os.path.join(self.metadata.data, "groups.xml"),
                           self.metadata.groups_xml.data,
                           "metadata")
        if self.has_all_xincludes("clients.xml"):
            self.check_xml(os.path.join(self.metadata.data, "clients.xml"),
                           self.metadata.clients_xml.data,
                           "metadata")

    def check_cfg(self):
        """ check Cfg files for required headers """
        if 'Cfg' in self.core.plugins:
            for entryset in self.core.plugins['Cfg'].entries.values():
                for entry in entryset.entries.values():
                    if entry.name.endswith(".genshi"):
                        rtype = "tgenshi"
                    else:
                        rtype = "cfg"
                    self.check_plaintext(entry.name, entry.data, rtype)

    def check_infoxml(self):
        """ check info.xml files for required headers """
        if 'Cfg' in self.core.plugins:
            for entryset in self.core.plugins['Cfg'].entries.items():
                if (hasattr(entryset, "infoxml") and
                    entryset.infoxml is not None):
                    self.check_xml(entryset.infoxml.name,
                                   entryset.infoxml.pnode.data,
                                   "infoxml")

    def check_probes(self):
        """ check probes for required headers """
        if 'Probes' in self.core.plugins:
            for probe in self.core.plugins['Probes'].probes.entries.values():
                self.check_plaintext(probe.name, probe.data, "probes")

    def check_xml(self, filename, xdata, rtype):
        """ check generic XML files for required headers """
        self.check_lines(filename,
                         [str(el)
                          for el in xdata.getiterator(lxml.etree.Comment)],
                         rtype)

    def check_plaintext(self, filename, data, rtype):
        """ check generic plaintex files for required headers """
        self.check_lines(filename, data.splitlines(), rtype)

    def check_lines(self, filename, lines, rtype):
        """ generic header check for a set of lines """
        if self.HandlesFile(filename):
            # found is trivalent:
            # False == not found
            # None == found but not expanded
            # True == found and expanded
            found = dict((k, False) for k in self.required_keywords(rtype))
            
            for line in lines:
                # we check for both '$<keyword>:' and '$<keyword>$' to see
                # if the keyword just hasn't been expanded
                for (keyword, status) in found.items():
                    if not status:
                        if '$%s:' % keyword in line:
                            found[keyword] = True
                        elif '$%s$' % keyword in line:
                            found[keyword] = None

            unexpanded = [keyword for (keyword, status) in found.items()
                          if status is None]
            if unexpanded:
                self.LintError("unexpanded-keywords",
                               "%s: Required keywords(s) found but not expanded: %s" %
                               (filename, ", ".join(unexpanded)))
            missing = [keyword for (keyword, status) in found.items()
                       if status is False]
            if missing:
                self.LintError("keywords-not-found",
                               "%s: Required keywords(s) not found: $%s$" %
                               (filename, "$, $".join(missing)))

            # next, check for required comments.  found is just
            # boolean
            found = dict((k, False) for k in self.required_comments(rtype))
            
            for line in lines:
                for (comment, status) in found.items():
                    if not status:
                        found[comment] = comment in line

            missing = [comment for (comment, status) in found.items()
                       if status is False]
            if missing:
                self.LintError("comments-not-found",
                               "%s: Required comments(s) not found: %s" %
                               (filename, ", ".join(missing)))

    def has_all_xincludes(self, mfile):
        """ return true if self.files includes all XIncludes listed in
        the specified metadata type, false otherwise"""
        if self.files is None:
            return True
        else:
            path = os.path.join(self.metadata.data, mfile)
            if path in self.files:
                xdata = lxml.etree.parse(path)
                for el in xdata.findall('./{http://www.w3.org/2001/XInclude}include'):
                    if not self.has_all_xincludes(el.get('href')):
                        self.LintError("broken-xinclude-chain",
                                       "Broken XInclude chain: could not include %s" % path)
                        return False

                return True

