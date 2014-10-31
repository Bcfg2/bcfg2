""" ``bcfg2-lint`` plugin for :ref:`Metadata
<server-plugins-grouping-metadata>` """

from Bcfg2.Server.Lint import ServerPlugin


class Metadata(ServerPlugin):
    """ ``bcfg2-lint`` plugin for :ref:`Metadata
    <server-plugins-grouping-metadata>`.  This checks for several things:

    * ``<Client>`` tags nested inside other ``<Client>`` tags;
    * Deprecated options (like ``location="floating"``);
    * Profiles that don't exist, or that aren't profile groups;
    * Groups or clients that are defined multiple times;
    * Multiple default groups or a default group that isn't a profile
      group.
    """
    __serverplugin__ = 'Metadata'

    def Run(self):
        self.nested_clients()
        self.deprecated_options()
        self.bogus_profiles()
        self.duplicate_groups()
        self.duplicate_default_groups()
        self.duplicate_clients()
        self.default_is_profile()

    @classmethod
    def Errors(cls):
        return {"nested-client-tags": "warning",
                "deprecated-clients-options": "warning",
                "nonexistent-profile-group": "error",
                "non-profile-set-as-profile": "error",
                "duplicate-group": "error",
                "duplicate-client": "error",
                "multiple-default-groups": "error",
                "default-is-not-profile": "error"}

    def deprecated_options(self):
        """ Check for the ``location='floating'`` option, which has
        been deprecated in favor of ``floating='true'``. """
        if not hasattr(self.metadata, "clients_xml"):
            # using metadata database
            return
        clientdata = self.metadata.clients_xml.xdata
        for el in clientdata.xpath("//Client"):
            loc = el.get("location")
            if loc:
                if loc == "floating":
                    floating = True
                else:
                    floating = False
                self.LintError("deprecated-clients-options",
                               "The location='%s' option is deprecated.  "
                               "Please use floating='%s' instead:\n%s" %
                               (loc, floating, self.RenderXML(el)))

    def nested_clients(self):
        """ Check for a ``<Client/>`` tag inside a ``<Client/>`` tag,
        which is either redundant or will never match. """
        groupdata = self.metadata.groups_xml.xdata
        for el in groupdata.xpath("//Client//Client"):
            self.LintError("nested-client-tags",
                           "Client %s nested within Client tag: %s" %
                           (el.get("name"), self.RenderXML(el)))

    def bogus_profiles(self):
        """ Check for clients that have profiles that are either not
        flagged as profile groups in ``groups.xml``, or don't exist. """
        if not hasattr(self.metadata, "clients_xml"):
            # using metadata database
            return
        for client in self.metadata.clients_xml.xdata.findall('.//Client'):
            profile = client.get("profile")
            if profile not in self.metadata.groups:
                self.LintError("nonexistent-profile-group",
                               "%s has nonexistent profile group %s:\n%s" %
                               (client.get("name"), profile,
                                self.RenderXML(client)))
            elif not self.metadata.groups[profile].is_profile:
                self.LintError("non-profile-set-as-profile",
                               "%s is set as profile for %s, but %s is not a "
                               "profile group:\n%s" %
                               (profile, client.get("name"), profile,
                                self.RenderXML(client)))

    def duplicate_default_groups(self):
        """ Check for multiple default groups. """
        defaults = []
        for grp in self.metadata.groups_xml.xdata.xpath("//Groups/Group") + \
                self.metadata.groups_xml.xdata.xpath("//Groups/Group//Group"):
            if grp.get("default", "false").lower() == "true":
                defaults.append(self.RenderXML(grp))
        if len(defaults) > 1:
            self.LintError("multiple-default-groups",
                           "Multiple default groups defined:\n%s" %
                           "\n".join(defaults))

    def duplicate_clients(self):
        """ Check for clients that are defined more than once. """
        if not hasattr(self.metadata, "clients_xml"):
            # using metadata database
            return
        self.duplicate_entries(
            self.metadata.clients_xml.xdata.xpath("//Client"),
            "client")

    def duplicate_groups(self):
        """ Check  for groups that  are defined more than  once. There
        are two ways this can happen:

        1. The group is listed twice with contradictory options.
        2. The group is listed with no options *first*, and then with
           options later.

        In this context, 'first' refers to the order in which groups
        are parsed; see the loop condition below and
        _handle_groups_xml_event above for details. """
        groups = dict()
        duplicates = dict()
        for grp in self.metadata.groups_xml.xdata.xpath("//Groups/Group") + \
                self.metadata.groups_xml.xdata.xpath("//Groups/Group//Group"):
            grpname = grp.get("name")
            if grpname in duplicates:
                duplicates[grpname].append(grp)
            elif len(grp.attrib) > 1:  # group has options
                if grpname in groups:
                    duplicates[grpname] = [grp, groups[grpname]]
                else:
                    groups[grpname] = grp
            else:  # group has no options
                groups[grpname] = grp
        for grpname, grps in duplicates.items():
            self.LintError("duplicate-group",
                           "Group %s is defined multiple times:\n%s" %
                           (grpname,
                            "\n".join(self.RenderXML(g) for g in grps)))

    def duplicate_entries(self, allentries, etype):
        """ Generic duplicate entry finder.

        :param allentries: A list of all entries to check for
                           duplicates.
        :type allentries: list of lxml.etree._Element
        :param etype: The entry type. This will be used to determine
                      the error name (``duplicate-<etype>``) and for
                      display to the end user.
        :type etype: string
        """
        entries = dict()
        for el in allentries:
            if el.get("name") in entries:
                entries[el.get("name")].append(self.RenderXML(el))
            else:
                entries[el.get("name")] = [self.RenderXML(el)]
        for ename, els in entries.items():
            if len(els) > 1:
                self.LintError("duplicate-%s" % etype,
                               "%s %s is defined multiple times:\n%s" %
                               (etype.title(), ename, "\n".join(els)))

    def default_is_profile(self):
        """ Ensure that the default group is a profile group. """
        if (self.metadata.default and
                not self.metadata.groups[self.metadata.default].is_profile):
            xdata = \
                self.metadata.groups_xml.xdata.xpath("//Group[@name='%s']" %
                                                     self.metadata.default)[0]
            self.LintError("default-is-not-profile",
                           "Default group is not a profile group:\n%s" %
                           self.RenderXML(xdata))
