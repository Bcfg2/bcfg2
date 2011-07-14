import os.path
import lxml.etree
import Bcfg2.Server.Lint

class Duplicates(Bcfg2.Server.Lint.ServerPlugin):
    """ Find duplicate clients, groups, etc. """
    def __init__(self, *args, **kwargs):
        Bcfg2.Server.Lint.ServerPlugin.__init__(self, *args, **kwargs)
        self.groups_xdata = None
        self.clients_xdata = None
        self.load_xdata()

    def Run(self):
        """ run plugin """
        # only run this plugin if we were not given a list of files.
        # not only is it marginally silly to run this plugin with a
        # partial list of files, it turns out to be really freaking
        # hard to get only a fragment of group or client metadata
        if self.groups_xdata is not None:
            self.duplicate_groups()
            self.duplicate_defaults()
        if self.clients_xdata is not None:
            self.duplicate_clients()

    def load_xdata(self):
        """ attempt to load XML data for groups and clients.  only
        actually load data if all documents reference in XIncludes can
        be found in self.files"""
        if self.has_all_xincludes("groups.xml"):
            self.groups_xdata = self.metadata.clients_xml.xdata
        if self.has_all_xincludes("clients.xml"):
            self.clients_xdata = self.metadata.clients_xml.xdata
            
    def duplicate_groups(self):
        """ find duplicate groups """
        self.duplicate_entries(self.clients_xdata.xpath('//Groups/Group'),
                               'group')

    def duplicate_clients(self):
        """ find duplicate clients """
        self.duplicate_entries(self.clients_xdata.xpath('//Clients/Client'),
                               'client')

    def duplicate_entries(self, data, etype):
        """ generic duplicate entry finder """
        seen = {}
        for el in data:
            if el.get('name') not in seen:
                seen[el.get('name')] = el
            else:
                self.LintError("duplicate-%s" % etype,
                               "Duplicate %s '%s':\n%s\n%s" %
                               (etype, el.get('name'),
                                self.RenderXML(seen[el.get('name')]),
                                self.RenderXML(el)))

    def duplicate_defaults(self):
        """ check for multiple default group definitions """
        default_groups = [g for g in self.groups_xdata.findall('.//Group')
                          if g.get('default') == 'true']
        if len(default_groups) > 1:
            self.LintError("multiple-default-groups",
                           "Multiple default groups defined: %s" %
                           ",".join(default_groups))

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
