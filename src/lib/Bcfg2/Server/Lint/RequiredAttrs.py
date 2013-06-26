""" Verify attributes for configuration entries that cannot be
verified with an XML schema alone. """

import os
import re
import lxml.etree
import Bcfg2.Server.Lint
import Bcfg2.Client.Tools.VCS
from Bcfg2.Server.Plugins.Packages import Apt, Yum
from Bcfg2.Client.Tools.POSIX.base import device_map
try:
    from Bcfg2.Server.Plugins.Bundler import BundleTemplateFile
    HAS_GENSHI = True
except ImportError:
    HAS_GENSHI = False


# format verifying functions.  TODO: These should be moved into XML
# schemas where possible.
def is_filename(val):
    """ Return True if val is a string describing a valid full path
    """
    return val.startswith("/") and len(val) > 1


def is_selinux_type(val):
    """ Return True if val is a string describing a valid (although
    not necessarily existent) SELinux type """
    return re.match(r'^[a-z_]+_t', val)


def is_selinux_user(val):
    """ Return True if val is a string describing a valid (although
    not necessarily existent) SELinux user """
    return re.match(r'^[a-z_]+_u', val)


def is_octal_mode(val):
    """ Return True if val is a string describing a valid octal
    permissions mode """
    return re.match(r'[0-7]{3,4}', val)


def is_username(val):
    """ Return True if val is a string giving either a positive
    integer uid, or a valid Unix username """
    return re.match(r'^([A-z][-_A-z0-9]{0,30}|\d+)$', val)


def is_device_mode(val):
    """ Return True if val is a string describing a positive integer
    """
    return re.match(r'^\d+$', val)


class RequiredAttrs(Bcfg2.Server.Lint.ServerPlugin):
    """ Verify attributes for configuration entries that cannot be
    verified with an XML schema alone. """
    def __init__(self, *args, **kwargs):
        Bcfg2.Server.Lint.ServerPlugin.__init__(self, *args, **kwargs)
        self.required_attrs = dict(
            Path=dict(
                device=dict(name=is_filename,
                            owner=is_username,
                            group=is_username,
                            dev_type=lambda v: v in device_map),
                directory=dict(name=is_filename, owner=is_username,
                               group=is_username, mode=is_octal_mode),
                file=dict(name=is_filename, owner=is_username,
                          group=is_username, mode=is_octal_mode,
                          __text__=None),
                hardlink=dict(name=is_filename, to=is_filename),
                symlink=dict(name=is_filename),
                ignore=dict(name=is_filename),
                nonexistent=dict(name=is_filename),
                permissions=dict(name=is_filename, owner=is_username,
                                 group=is_username, mode=is_octal_mode),
                vcs=dict(vcstype=lambda v: (v != 'Path' and
                                            hasattr(Bcfg2.Client.Tools.VCS.VCS,
                                                    "Install%s" % v)),
                         revision=None, sourceurl=None)),
            Service={"__any__": dict(name=None),
                     "smf": dict(name=None, FMRI=None)},
            Action={None: dict(name=None,
                               timing=lambda v: v in ['pre', 'post', 'both'],
                               when=lambda v: v in ['modified', 'always'],
                               status=lambda v: v in ['ignore', 'check'],
                               command=None)},
            ACL=dict(
                default=dict(scope=lambda v: v in ['user', 'group'],
                             perms=lambda v: re.match(r'^([0-7]|[rwx\-]{0,3}',
                                                      v)),
                access=dict(scope=lambda v: v in ['user', 'group'],
                            perms=lambda v: re.match(r'^([0-7]|[rwx\-]{0,3}',
                                                     v)),
                mask=dict(perms=lambda v: re.match(r'^([0-7]|[rwx\-]{0,3}',
                                                   v))),
            Package={"__any__": dict(name=None)},
            SEBoolean={None: dict(name=None,
                                  value=lambda v: v in ['on', 'off'])},
            SEModule={None: dict(name=None, __text__=None)},
            SEPort={
                None: dict(name=lambda v: re.match(r'^\d+(-\d+)?/(tcp|udp)',
                                                   v),
                           selinuxtype=is_selinux_type)},
            SEFcontext={None: dict(name=None, selinuxtype=is_selinux_type)},
            SENode={None: dict(name=lambda v: "/" in v,
                               selinuxtype=is_selinux_type,
                               proto=lambda v: v in ['ipv6', 'ipv4'])},
            SELogin={None: dict(name=is_username,
                                selinuxuser=is_selinux_user)},
            SEUser={None: dict(name=is_selinux_user,
                               roles=lambda v: all(is_selinux_user(u)
                                                   for u in " ".split(v)),
                               prefix=None)},
            SEInterface={None: dict(name=None, selinuxtype=is_selinux_type)},
            SEPermissive={None: dict(name=is_selinux_type)},
            POSIXGroup={None: dict(name=is_username)},
            POSIXUser={None: dict(name=is_username)})

    def Run(self):
        self.check_packages()
        if "Defaults" in self.core.plugins:
            self.logger.info("Defaults plugin enabled; skipping required "
                             "attribute checks")
        else:
            self.check_rules()
            self.check_bundles()

    @classmethod
    def Errors(cls):
        return {"unknown-entry-type": "error",
                "unknown-entry-tag": "error",
                "required-attrs-missing": "error",
                "required-attr-format": "error",
                "extra-attrs": "warning"}

    def check_packages(self):
        """ Check Packages sources for Source entries with missing
        attributes. """
        if 'Packages' not in self.core.plugins:
            return

        for source in self.core.plugins['Packages'].sources:
            if isinstance(source, Yum.YumSource):
                if (not source.pulp_id and not source.url and
                    not source.rawurl):
                    self.LintError(
                        "required-attrs-missing",
                        "A %s source must have either a url, rawurl, or "
                        "pulp_id attribute: %s" %
                        (source.ptype, self.RenderXML(source.xsource)))
            elif not source.url and not source.rawurl:
                self.LintError(
                    "required-attrs-missing",
                    "A %s source must have either a url or rawurl attribute: "
                    "%s" %
                    (source.ptype, self.RenderXML(source.xsource)))

            if (not isinstance(source, Apt.AptSource) and
                source.recommended):
                self.LintError(
                    "extra-attrs",
                    "The recommended attribute is not supported on %s sources:"
                    " %s" %
                    (source.ptype, self.RenderXML(source.xsource)))

    def check_rules(self):
        """ check Rules for Path entries with missing attrs """
        if 'Rules' not in self.core.plugins:
            return

        for rules in self.core.plugins['Rules'].entries.values():
            xdata = rules.pnode.data
            for path in xdata.xpath("//Path"):
                self.check_entry(path, os.path.join(self.config['repo'],
                                                    rules.name))

    def check_bundles(self):
        """ Check bundles for BoundPath entries with missing
        attrs. """
        if 'Bundler' not in self.core.plugins:
            return

        for bundle in self.core.plugins['Bundler'].entries.values():
            if (self.HandlesFile(bundle.name) and
                (not HAS_GENSHI or
                 not isinstance(bundle, BundleTemplateFile))):
                try:
                    xdata = lxml.etree.XML(bundle.data)
                except (lxml.etree.XMLSyntaxError, AttributeError):
                    xdata = \
                        lxml.etree.parse(bundle.template.filepath).getroot()

                for path in \
                        xdata.xpath("//*[substring(name(), 1, 5) = 'Bound']"):
                    self.check_entry(path, bundle.name)

    def check_entry(self, entry, filename):
        """ Generic entry check.

        :param entry: The XML entry to check for missing attributes.
        :type entry: lxml.etree._Element
        :param filename: The filename the entry came from
        :type filename: string
        """
        if self.HandlesFile(filename):
            name = entry.get('name')
            tag = entry.tag
            if tag.startswith("Bound"):
                tag = tag[5:]
            if tag not in self.required_attrs:
                self.LintError("unknown-entry-tag",
                               "Unknown entry tag '%s': %s" %
                               (tag, self.RenderXML(entry)))
                return

            etype = entry.get('type')
            if etype in self.required_attrs[tag]:
                required_attrs = self.required_attrs[tag][etype]
            elif '__any__' in self.required_attrs[tag]:
                required_attrs = self.required_attrs[tag]['__any__']
            else:
                self.LintError("unknown-entry-type",
                               "Unknown %s type %s: %s" %
                               (tag, etype, self.RenderXML(entry)))
                return
            attrs = set(entry.attrib.keys())

            if 'dev_type' in required_attrs:
                dev_type = entry.get('dev_type')
                if dev_type in ['block', 'char']:
                    # check if major/minor are specified
                    required_attrs['major'] = is_device_mode
                    required_attrs['minor'] = is_device_mode

            if tag == 'ACL' and 'scope' in required_attrs:
                required_attrs[entry.get('scope')] = is_username

            if '__text__' in required_attrs:
                fmt = required_attrs['__text__']
                del required_attrs['__text__']
                if (not entry.text and
                    not entry.get('empty', 'false').lower() == 'true'):
                    self.LintError("required-attrs-missing",
                                   "Text missing for %s %s in %s: %s" %
                                   (tag, name, filename,
                                    self.RenderXML(entry)))
                if fmt is not None and not fmt(entry.text):
                    self.LintError(
                        "required-attr-format",
                        "Text content of %s %s in %s is malformed\n%s" %
                        (tag, name, filename, self.RenderXML(entry)))

            if not attrs.issuperset(required_attrs.keys()):
                self.LintError(
                    "required-attrs-missing",
                    "The following required attribute(s) are missing for %s "
                    "%s in %s: %s\n%s" %
                    (tag, name, filename,
                     ", ".join([attr
                                for attr in
                                set(required_attrs.keys()).difference(attrs)]),
                     self.RenderXML(entry)))

            for attr, fmt in required_attrs.items():
                if fmt and attr in attrs and not fmt(entry.attrib[attr]):
                    self.LintError(
                        "required-attr-format",
                        "The %s attribute of %s %s in %s is malformed\n%s" %
                        (attr, tag, name, filename, self.RenderXML(entry)))
