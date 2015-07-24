""" Subcommands and helpers for bcfg2-admin """

import os
import sys
import time
import glob
import stat
import random
import socket
import string
import getpass
import difflib
import tarfile
import argparse
import lxml.etree
import Bcfg2.Logger
import Bcfg2.Options
import Bcfg2.DBSettings
import Bcfg2.Server.Core
import Bcfg2.Client.Proxy
from Bcfg2.Server.Plugin import PullSource, Generator, MetadataConsistencyError
from Bcfg2.Utils import hostnames2ranges, Executor, safe_input
import Bcfg2.Server.Plugins.Metadata

try:
    from django.core.exceptions import ImproperlyConfigured
    from django.core import management
    import django
    import django.conf
    import Bcfg2.Server.models

    HAS_DJANGO = True
    if django.VERSION[0] == 1 and django.VERSION[1] >= 7:
        HAS_REPORTS = True
    else:
        try:
            import south  # pylint: disable=W0611
            HAS_REPORTS = True
        except ImportError:
            HAS_REPORTS = False
except ImportError:
    HAS_DJANGO = False
    HAS_REPORTS = False


class ccolors:  # pylint: disable=C0103,W0232
    """ ANSI color escapes to make colorizing text easier """
    # pylint: disable=W1401
    ADDED = '\033[92m'
    CHANGED = '\033[93m'
    REMOVED = '\033[91m'
    ENDC = '\033[0m'
    # pylint: enable=W1401

    @classmethod
    def disable(cls):
        """ Disable all coloration """
        cls.ADDED = ''
        cls.CHANGED = ''
        cls.REMOVED = ''
        cls.ENDC = ''


def gen_password(length):
    """Generates a random alphanumeric password with length characters."""
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for i in range(length))


def print_table(rows, justify='left', hdr=True, vdelim=" ", padding=1):
    """Pretty print a table

    rows - list of rows ([[row 1], [row 2], ..., [row n]])
    hdr - if True the first row is treated as a table header
    vdelim - vertical delimiter between columns
    padding - # of spaces around the longest element in the column
    justify - may be left,center,right

    """
    hdelim = "="
    justify = {'left': str.ljust,
               'center': str.center,
               'right': str.rjust}[justify.lower()]

    # Calculate column widths (longest item in each column
    # plus padding on both sides)
    cols = list(zip(*rows))
    col_widths = [max([len(str(item)) + 2 * padding
                       for item in col]) for col in cols]
    borderline = vdelim.join([w * hdelim for w in col_widths])

    # Print out the table
    print(borderline)
    for row in rows:
        print(vdelim.join([justify(str(item), width)
                           for (item, width) in zip(row, col_widths)]))
        if hdr:
            print(borderline)
            hdr = False


class AdminCmd(Bcfg2.Options.Subcommand):  # pylint: disable=W0223
    """ Base class for all bcfg2-admin modes """
    def setup(self):
        """ Perform post-init (post-options parsing), pre-run setup
        tasks """
        pass

    def errExit(self, emsg):
        """ exit with an error """
        print(emsg)
        raise SystemExit(1)


class _ServerAdminCmd(AdminCmd):  # pylint: disable=W0223
    """ Base class for admin modes that run a Bcfg2 server. """
    __plugin_whitelist__ = None
    __plugin_blacklist__ = None

    options = AdminCmd.options + Bcfg2.Server.Core.Core.options

    def __init__(self):
        AdminCmd.__init__(self)
        self.metadata = None

    def setup(self):
        if self.__plugin_whitelist__ is not None:
            Bcfg2.Options.setup.plugins = [
                p for p in Bcfg2.Options.setup.plugins
                if p.name in self.__plugin_whitelist__]
        elif self.__plugin_blacklist__ is not None:
            Bcfg2.Options.setup.plugins = [
                p for p in Bcfg2.Options.setup.plugins
                if p.name not in self.__plugin_blacklist__]

        try:
            self.core = Bcfg2.Server.Core.Core()
        except Bcfg2.Server.Core.CoreInitError:
            msg = sys.exc_info()[1]
            self.errExit("Core load failed: %s" % msg)
        self.core.load_plugins()
        self.core.fam.handle_event_set()
        self.metadata = self.core.metadata

    def shutdown(self):
        self.core.shutdown()


class _ProxyAdminCmd(AdminCmd):  # pylint: disable=W0223
    """ Base class for admin modes that proxy to a running Bcfg2 server """

    options = AdminCmd.options + Bcfg2.Client.Proxy.ComponentProxy.options

    def __init__(self):
        AdminCmd.__init__(self)
        self.proxy = None

    def setup(self):
        self.proxy = Bcfg2.Client.Proxy.ComponentProxy()


class Backup(AdminCmd):
    """ Make a backup of the Bcfg2 repository """

    options = AdminCmd.options + [Bcfg2.Options.Common.repository]

    def run(self, setup):
        timestamp = time.strftime('%Y%m%d%H%M%S')
        datastore = setup.repository
        fmt = 'gz'
        mode = 'w:' + fmt
        filename = timestamp + '.tar' + '.' + fmt
        out = tarfile.open(os.path.join(datastore, filename), mode=mode)
        out.add(datastore, os.path.basename(datastore))
        out.close()
        print("Archive %s was stored under %s" % (filename, datastore))


class Client(_ServerAdminCmd):
    """ Create, modify, delete, or list client entries """

    __plugin_whitelist__ = ["Metadata"]
    options = _ServerAdminCmd.options + [
        Bcfg2.Options.PositionalArgument(
            "mode",
            choices=["add", "del", "delete", "remove", "rm", "up", "update",
                     "list"]),
        Bcfg2.Options.PositionalArgument("hostname", nargs='?'),
        Bcfg2.Options.PositionalArgument("attributes", metavar="KEY=VALUE",
                                         nargs='*')]

    valid_attribs = ['profile', 'uuid', 'password', 'floating', 'secure',
                     'address', 'auth']

    def get_attribs(self, setup):
        """ Get attributes for adding or updating a client from the command
        line """
        attr_d = {}
        for i in setup.attributes:
            attr, val = i.split('=', 1)
            if attr not in self.valid_attribs:
                print("Attribute %s unknown. Valid attributes: %s" %
                      (attr, self.valid_attribs))
                raise SystemExit(1)
            attr_d[attr] = val
        return attr_d

    def run(self, setup):
        if setup.mode != 'list' and not setup.hostname:
            self.parser.error("<hostname> is required in %s mode" % setup.mode)
        elif setup.mode == 'list' and setup.hostname:
            self.logger.warning("<hostname> is not honored in list mode")

        if setup.mode == 'list':
            for client in self.metadata.list_clients():
                print(client)
        else:
            include_attribs = True
            if setup.mode == 'add':
                func = self.metadata.add_client
                action = "adding"
            elif setup.mode in ['up', 'update']:
                func = self.metadata.update_client
                action = "updating"
            elif setup.mode in ['del', 'delete', 'rm', 'remove']:
                func = self.metadata.remove_client
                include_attribs = False
                action = "deleting"

            if include_attribs:
                args = (setup.hostname, self.get_attribs(setup))
            else:
                args = (setup.hostname,)
            try:
                func(*args)
            except MetadataConsistencyError:
                err = sys.exc_info()[1]
                self.errExit("Error %s client %s: %s" % (setup.hostname,
                                                         action, err))


class Compare(AdminCmd):
    """ Compare two hosts or two versions of a host specification """

    help = "Given two XML files (as produced by bcfg2-info build or bcfg2 " + \
        "-qnc) or two directories containing XML files (as produced by " + \
        "bcfg2-info buildall or bcfg2-info builddir), output a detailed, " + \
        "Bcfg2-centric diff."

    options = AdminCmd.options + [
        Bcfg2.Options.Option(
            "-d", "--diff-lines", type=int,
            help="Show only N lines of a diff"),
        Bcfg2.Options.BooleanOption(
            "-c", "--color", help="Use colors even if not run from a TTY"),
        Bcfg2.Options.BooleanOption(
            "-q", "--quiet",
            help="Only show that entries differ, not how they differ"),
        Bcfg2.Options.PathOption("path1", metavar="<file-or-dir>"),
        Bcfg2.Options.PathOption("path2", metavar="<file-or-dir>")]

    changes = dict()

    def removed(self, msg, host):
        """ Record a removed element """
        self.record("%sRemoved: %s%s" % (ccolors.REMOVED, msg, ccolors.ENDC),
                    host)

    def added(self, msg, host):
        """ Record an removed element """
        self.record("%sAdded: %s%s" % (ccolors.ADDED, msg, ccolors.ENDC), host)

    def changed(self, msg, host):
        """ Record a changed element """
        self.record("%sChanged: %s%s" % (ccolors.CHANGED, msg, ccolors.ENDC),
                    host)

    def record(self, msg, host):
        """ Record a new removed/added/changed message for the given
        host """
        if msg not in self.changes:
            self.changes[msg] = [host]
        else:
            self.changes[msg].append(host)

    def udiff(self, lines1, lines2, **kwargs):
        """ get a unified diff with control lines stripped """
        lines = None
        if "lines" in kwargs:
            if kwargs['lines'] is not None:
                lines = int(kwargs['lines'])
            del kwargs['lines']
        if lines == 0:
            return []
        kwargs['n'] = 0
        diff = []
        for line in difflib.unified_diff(lines1, lines2, **kwargs):
            if (line.startswith("--- ") or line.startswith("+++ ") or
                    line.startswith("@@ ")):
                continue
            if lines is not None and len(diff) > lines:
                diff.append("  ...")
                break
            if line.startswith("+"):
                diff.extend("  %s%s%s" % (ccolors.ADDED, l, ccolors.ENDC)
                            for l in line.splitlines())
            elif line.startswith("-"):
                diff.extend("  %s%s%s" % (ccolors.REMOVED, l, ccolors.ENDC)
                            for l in line.splitlines())
        return diff

    def _bundletype(self, el):
        """ Get a human-friendly representation of the type of the
        given bundle -- independent or not """
        if el.get("tag") == "Independent":
            return "Independent bundle"
        else:
            return "Bundle"

    def _get_filelists(self, setup):
        """ Get a list of 2-tuples of files to compare """
        files = []
        if os.path.isdir(setup.path1) and os.path.isdir(setup.path1):
            for fpath in glob.glob(os.path.join(setup.path1, '*')):
                fname = os.path.basename(fpath)
                if os.path.exists(os.path.join(setup.path2, fname)):
                    files.append((os.path.join(setup.path1, fname),
                                  os.path.join(setup.path2, fname)))
                else:
                    if fname.endswith(".xml"):
                        host = fname[0:-4]
                    else:
                        host = fname
                    self.removed(host, '')
            for fpath in glob.glob(os.path.join(setup.path2, '*')):
                fname = os.path.basename(fpath)
                if not os.path.exists(os.path.join(setup.path1, fname)):
                    if fname.endswith(".xml"):
                        host = fname[0:-4]
                    else:
                        host = fname
                    self.added(host, '')
        elif os.path.isfile(setup.path1) and os.path.isfile(setup.path2):
            files.append((setup.path1, setup.path2))
        else:
            self.errExit("Cannot diff a file and a directory")
        return files

    def run(self, setup):  # pylint: disable=R0912,R0914,R0915
        if not sys.stdout.isatty() and not setup.color:
            ccolors.disable()

        files = self._get_filelists(setup)
        for file1, file2 in files:
            host = None
            if os.path.basename(file1) == os.path.basename(file2):
                fname = os.path.basename(file1)
                if fname.endswith(".xml"):
                    host = fname[0:-4]
                else:
                    host = fname

            xdata1 = lxml.etree.parse(file1).getroot()
            xdata2 = lxml.etree.parse(file2).getroot()

            elements1 = dict()
            elements2 = dict()
            bundles1 = [el.get("name") for el in xdata1.iterchildren()]
            bundles2 = [el.get("name") for el in xdata2.iterchildren()]
            for el in xdata1.iterchildren():
                if el.get("name") not in bundles2:
                    self.removed("%s %s" % (self._bundletype(el),
                                            el.get("name")),
                                 host)
            for el in xdata2.iterchildren():
                if el.get("name") not in bundles1:
                    self.added("%s %s" % (self._bundletype(el),
                                          el.get("name")),
                               host)

            for bname in bundles1:
                bundle = xdata1.find("*[@name='%s']" % bname)
                for el in bundle.getchildren():
                    elements1["%s:%s" % (el.tag, el.get("name"))] = el
            for bname in bundles2:
                bundle = xdata2.find("*[@name='%s']" % bname)
                for el in bundle.getchildren():
                    elements2["%s:%s" % (el.tag, el.get("name"))] = el

            for el in elements1.values():
                elid = "%s:%s" % (el.tag, el.get("name"))
                if elid not in elements2:
                    self.removed("Element %s" % elid, host)
                else:
                    el2 = elements2[elid]
                    if (el.getparent().get("name") !=
                            el2.getparent().get("name")):
                        self.changed(
                            "Element %s was in bundle %s, "
                            "now in bundle %s" % (elid,
                                                  el.getparent().get("name"),
                                                  el2.getparent().get("name")),
                            host)
                    attr1 = sorted(["%s=\"%s\"" % (attr, el.get(attr))
                                    for attr in el.attrib])
                    attr2 = sorted(["%s=\"%s\"" % (attr, el.get(attr))
                                    for attr in el2.attrib])
                    if attr1 != attr2:
                        err = ["Element %s has different attributes" % elid]
                        if not setup.quiet:
                            err.extend(self.udiff(attr1, attr2))
                        self.changed("\n".join(err), host)

                    if el.text != el2.text:
                        if el.text is None:
                            self.changed("Element %s content was added" % elid,
                                         host)
                        elif el2.text is None:
                            self.changed("Element %s content was removed" %
                                         elid, host)
                        else:
                            err = ["Element %s has different content" %
                                   elid]
                            if not setup.quiet:
                                err.extend(
                                    self.udiff(el.text.splitlines(),
                                               el2.text.splitlines(),
                                               lines=setup.diff_lines))
                            self.changed("\n".join(err), host)

            for el in elements2.values():
                elid = "%s:%s" % (el.tag, el.get("name"))
                if elid not in elements2:
                    self.removed("Element %s" % elid, host)

        for change, hosts in self.changes.items():
            hlist = [h for h in hosts if h is not None]
            if len(files) > 1 and len(hlist):
                print("===== %s =====" %
                      "\n      ".join(hostnames2ranges(hlist)))
            print(change)
            if len(files) > 1 and len(hlist):
                print("")


class ExpireCache(_ProxyAdminCmd):
    """ Expire the metadata cache """

    options = _ProxyAdminCmd.options + [
        Bcfg2.Options.PositionalArgument(
            "hostname", nargs="*", default=[],
            help="Expire cache for the given host(s)")]

    def run(self, setup):
        clients = None
        if setup.hostname is not None and len(setup.hostname) > 0:
            clients = setup.hostname

        try:
            self.proxy.expire_metadata_cache(clients)
        except Bcfg2.Client.Proxy.ProxyError:
            self.errExit("Proxy Error: %s" % sys.exc_info()[1])


class Init(AdminCmd):
    """Interactively initialize a new repository."""

    options = AdminCmd.options + [
        Bcfg2.Options.Common.repository, Bcfg2.Options.Common.plugins]

    # default config file
    config = '''[server]
repository = %s
plugins = %s
# Uncomment the following to listen on all interfaces
#listen_all = true

[database]
#engine = sqlite3
# 'postgresql', 'mysql', 'mysql_old', 'sqlite3' or 'ado_mssql'.
#name =
# Or path to database file if using sqlite3.
#<repository>/etc/bcfg2.sqlite is default path if left empty
#user =
# Not used with sqlite3.
#password =
# Not used with sqlite3.
#host =
# Not used with sqlite3.
#port =

[reporting]
transport = LocalFilesystem

[communication]
password = %s
certificate = %s
key = %s
ca = %s

[components]
bcfg2 = %s
'''

    # Default groups
    groups = '''<Groups>
  <Group profile='true' public='true' default='true' name='basic'/>
</Groups>
'''

    # Default contents of clients.xml
    clients = '''<Clients>
  <Client profile="basic" name="%s"/>
</Clients>
'''

    def __init__(self):
        AdminCmd.__init__(self)
        self.data = dict()

    def _set_defaults(self, setup):
        """Set default parameters."""
        self.data['plugins'] = setup.plugins
        self.data['configfile'] = setup.config
        self.data['repopath'] = setup.repository
        self.data['password'] = gen_password(8)
        self.data['shostname'] = socket.getfqdn()
        self.data['server_uri'] = "https://%s:6789" % self.data['shostname']
        self.data['country'] = 'US'
        self.data['state'] = 'Illinois'
        self.data['location'] = 'Argonne'
        if os.path.exists("/etc/pki/tls"):
            self.data['keypath'] = "/etc/pki/tls/private/bcfg2.key"
            self.data['certpath'] = "/etc/pki/tls/certs/bcfg2.crt"
        elif os.path.exists("/etc/ssl"):
            self.data['keypath'] = "/etc/ssl/bcfg2.key"
            self.data['certpath'] = "/etc/ssl/bcfg2.crt"
        else:
            basepath = os.path.dirname(self.data['configfile'])
            self.data['keypath'] = os.path.join(basepath, "bcfg2.key")
            self.data['certpath'] = os.path.join(basepath, 'bcfg2.crt')

    def input_with_default(self, msg, default_name):
        """ Prompt for input with the given message, taking the
        default from ``self.data`` """
        val = safe_input("%s [%s]: " % (msg, self.data[default_name]))
        if val:
            self.data[default_name] = val

    def run(self, setup):
        self._set_defaults(setup)

        # Prompt the user for input
        self._prompt_server()
        self._prompt_config()
        self._prompt_repopath()
        self._prompt_password()
        self._prompt_keypath()
        self._prompt_certificate()

        # Initialize the repository
        self.init_repo()

    def _prompt_server(self):
        """Ask for the server name and URI."""
        self.input_with_default("What is the server's hostname", 'shostname')
        # reset default server URI
        self.data['server_uri'] = "https://%s:6789" % self.data['shostname']
        self.input_with_default("Server location", 'server_uri')

    def _prompt_config(self):
        """Ask for the configuration file path."""
        self.input_with_default("Path to Bcfg2 configuration", 'configfile')

    def _prompt_repopath(self):
        """Ask for the repository path."""
        while True:
            self.input_with_default("Location of Bcfg2 repository", 'repopath')
            if os.path.isdir(self.data['repopath']):
                response = safe_input("Directory %s exists. Overwrite? [y/N]:"
                                      % self.data['repopath'])
                if response.lower().strip() == 'y':
                    break
            else:
                break

    def _prompt_password(self):
        """Ask for a password or generate one if none is provided."""
        newpassword = getpass.getpass(
            "Input password used for communication verification "
            "(without echoing; leave blank for random): ").strip()
        if len(newpassword) != 0:
            self.data['password'] = newpassword

    def _prompt_certificate(self):
        """Ask for the key details (country, state, and location)."""
        print("The following questions affect SSL certificate generation.")
        print("If no data is provided, the default values are used.")
        self.input_with_default("Country code for certificate", 'country')
        self.input_with_default("State or Province Name (full name) for "
                                "certificate", 'state')
        self.input_with_default("Locality Name (e.g., city) for certificate",
                                'location')

    def _prompt_keypath(self):
        """ Ask for the key pair location.  Try to use sensible
        defaults depending on the OS """
        self.input_with_default("Path where Bcfg2 server private key will be "
                                "created", 'keypath')
        self.input_with_default("Path where Bcfg2 server cert will be created",
                                'certpath')

    def _init_plugins(self):
        """Initialize each plugin-specific portion of the repository."""
        for plugin in self.data['plugins']:
            kwargs = dict()
            if issubclass(plugin, Bcfg2.Server.Plugins.Metadata.Metadata):
                kwargs.update(
                    dict(groups_xml=self.groups,
                         clients_xml=self.clients % self.data['shostname']))
            plugin.init_repo(self.data['repopath'], **kwargs)

    def create_conf(self):
        """ create the config file """
        confdata = self.config % (
            self.data['repopath'],
            ','.join(p.__name__ for p in self.data['plugins']),
            self.data['password'],
            self.data['certpath'],
            self.data['keypath'],
            self.data['certpath'],
            self.data['server_uri'])

        # Don't overwrite existing bcfg2.conf file
        if os.path.exists(self.data['configfile']):
            result = safe_input("\nWarning: %s already exists. "
                                "Overwrite? [y/N]: " % self.data['configfile'])
            if result not in ['Y', 'y']:
                print("Leaving %s unchanged" % self.data['configfile'])
                return
        try:
            open(self.data['configfile'], "w").write(confdata)
            os.chmod(self.data['configfile'],
                     stat.S_IRUSR | stat.S_IWUSR)  # 0600
        except:  # pylint: disable=W0702
            self.errExit("Error trying to write configuration file '%s': %s" %
                         (self.data['configfile'], sys.exc_info()[1]))

    def init_repo(self):
        """Setup a new repo and create the content of the
        configuration file."""
        # Create the repository
        path = os.path.join(self.data['repopath'], 'etc')
        try:
            os.makedirs(path)
            self._init_plugins()
            print("Repository created successfuly in %s" %
                  self.data['repopath'])
        except OSError:
            print("Failed to create %s." % path)

        # Create the configuration file and SSL key
        self.create_conf()
        self.create_key()

    def create_key(self):
        """Creates a bcfg2.key at the directory specifed by keypath."""
        cmd = Executor(timeout=120)
        subject = "/C=%s/ST=%s/L=%s/CN=%s'" % (
            self.data['country'], self.data['state'], self.data['location'],
            self.data['shostname'])
        key = cmd.run(["openssl", "req", "-batch", "-x509", "-nodes",
                       "-subj", subject, "-days", "1000",
                       "-newkey", "rsa:2048",
                       "-keyout", self.data['keypath'], "-noout"])
        if not key.success:
            print("Error generating key: %s" % key.error)
            return
        os.chmod(self.data['keypath'], stat.S_IRUSR | stat.S_IWUSR)  # 0600
        csr = cmd.run(["openssl", "req", "-batch", "-new", "-subj", subject,
                       "-key", self.data['keypath']])
        if not csr.success:
            print("Error generating certificate signing request: %s" %
                  csr.error)
            return
        cert = cmd.run(["openssl", "x509", "-req", "-days", "1000",
                        "-signkey", self.data['keypath'],
                        "-out", self.data['certpath']],
                       inputdata=csr.stdout)
        if not cert.success:
            print("Error signing certificate: %s" % cert.error)
            return


class Minestruct(_ServerAdminCmd):
    """ Extract extra entry lists from statistics """

    options = _ServerAdminCmd.options + [
        Bcfg2.Options.PathOption(
            "-f", "--outfile", type=argparse.FileType('w'), default=sys.stdout,
            help="Write to the given file"),
        Bcfg2.Options.Option(
            "-g", "--groups", help="Only build config for groups",
            type=Bcfg2.Options.Types.colon_list, default=[]),
        Bcfg2.Options.PositionalArgument("hostname")]

    def run(self, setup):
        try:
            extra = set()
            for source in self.core.plugins_by_type(PullSource):
                for item in source.GetExtra(setup.hostname):
                    extra.add(item)
        except:  # pylint: disable=W0702
            self.errExit("Failed to find extra entry info for client %s: %s" %
                         (setup.hostname, sys.exc_info()[1]))
        root = lxml.etree.Element("Base")
        self.logger.info("Found %d extra entries" % len(extra))
        add_point = root
        for grp in setup.groups:
            add_point = lxml.etree.SubElement(add_point, "Group", name=grp)
        for tag, name in extra:
            self.logger.info("%s: %s" % (tag, name))
            lxml.etree.SubElement(add_point, tag, name=name)

        lxml.etree.ElementTree(root).write(setup.outfile, pretty_print=True)


class Perf(_ProxyAdminCmd):
    """ Get performance data from server """

    def run(self, setup):
        output = [('Name', 'Min', 'Max', 'Mean', 'Count')]
        data = self.proxy.get_statistics()
        for key in sorted(data.keys()):
            output.append(
                (key, ) +
                tuple(["%.06f" % item
                       for item in data[key][:-1]] + [data[key][-1]]))
        print_table(output)


class Pull(_ServerAdminCmd):
    """ Retrieves entries from clients and integrates the information
    into the repository """

    options = _ServerAdminCmd.options + [
        Bcfg2.Options.Common.interactive,
        Bcfg2.Options.BooleanOption(
            "-s", "--stdin",
            help="Read lists of <hostname> <entrytype> <entryname> from stdin "
            "instead of the command line"),
        Bcfg2.Options.PositionalArgument("hostname", nargs='?'),
        Bcfg2.Options.PositionalArgument("entrytype", nargs='?'),
        Bcfg2.Options.PositionalArgument("entryname", nargs='?')]

    def __init__(self):
        _ServerAdminCmd.__init__(self)
        self.interactive = False

    def setup(self):
        if (not Bcfg2.Options.setup.stdin and
            not (Bcfg2.Options.setup.hostname and
                 Bcfg2.Options.setup.entrytype and
                 Bcfg2.Options.setup.entryname)):
            print("You must specify either --stdin or a hostname, entry type, "
                  "and entry name on the command line.")
            self.errExit(self.usage())
        _ServerAdminCmd.setup(self)

    def run(self, setup):
        self.interactive = setup.interactive
        if setup.stdin:
            for line in sys.stdin:
                try:
                    self.PullEntry(*line.split(None, 3))
                except SystemExit:
                    print("  for %s" % line)
                except:
                    print("Bad entry: %s" % line.strip())
        else:
            self.PullEntry(setup.hostname, setup.entrytype, setup.entryname)

    def BuildNewEntry(self, client, etype, ename):
        """Construct a new full entry for
        given client/entry from statistics.
        """
        new_entry = {'type': etype, 'name': ename}
        pull_sources = self.core.plugins_by_type(PullSource)
        for plugin in pull_sources:
            try:
                (owner, group, mode, contents) = \
                    plugin.GetCurrentEntry(client, etype, ename)
                break
            except Bcfg2.Server.Plugin.PluginExecutionError:
                if plugin == pull_sources[-1]:
                    self.errExit("Pull Source failure; could not fetch "
                                 "current state")

        try:
            data = {'owner': owner,
                    'group': group,
                    'mode': mode,
                    'text': contents}
        except UnboundLocalError:
            self.errExit("Unable to build entry")
        for key, val in list(data.items()):
            if val:
                new_entry[key] = val
        return new_entry

    def Choose(self, choices):
        """Determine where to put pull data."""
        if self.interactive:
            for choice in choices:
                print("Plugin returned choice:")
                if id(choice) == id(choices[0]):
                    print("(current entry) ")
                if choice.all:
                    print(" => global entry")
                elif choice.group:
                    print(" => group entry: %s (prio %d)" %
                          (choice.group, choice.prio))
                else:
                    print(" => host entry: %s" % (choice.hostname))

                # flush input buffer
                ans = safe_input("Use this entry? [yN]: ") in ['y', 'Y']
                if ans:
                    return choice
            return False
        else:
            if not choices:
                return False
            return choices[0]

    def PullEntry(self, client, etype, ename):
        """Make currently recorded client state correct for entry."""
        new_entry = self.BuildNewEntry(client, etype, ename)

        meta = self.core.build_metadata(client)
        # Find appropriate plugin in core
        glist = [gen for gen in self.core.plugins_by_type(Generator)
                 if ename in gen.Entries.get(etype, {})]
        if len(glist) != 1:
            self.errExit("Got wrong numbers of matching generators for entry:"
                         "%s" % ([g.name for g in glist]))
        plugin = glist[0]
        if not isinstance(plugin, Bcfg2.Server.Plugin.PullTarget):
            self.errExit("Configuration upload not supported by plugin %s" %
                         plugin.name)
        try:
            choices = plugin.AcceptChoices(new_entry, meta)
            specific = self.Choose(choices)
            if specific:
                plugin.AcceptPullData(specific, new_entry, self.logger)
        except Bcfg2.Server.Plugin.PluginExecutionError:
            self.errExit("Configuration upload not supported by plugin %s" %
                         plugin.name)

        # Commit if running under a VCS
        for vcsplugin in list(self.core.plugins.values()):
            if isinstance(vcsplugin, Bcfg2.Server.Plugin.Version):
                files = "%s/%s" % (plugin.data, ename)
                comment = 'file "%s" pulled from host %s' % (files, client)
                vcsplugin.commit_data([files], comment)


class _ReportsCmd(AdminCmd):  # pylint: disable=W0223
    """ Base command for all admin modes dealing with the reporting
    subsystem """
    def __init__(self):
        AdminCmd.__init__(self)
        self.reports_entries = ()
        self.reports_classes = ()

    def setup(self):
        # this has to be imported after options are parsed, because
        # Django finalizes its settings as soon as it's loaded, which
        # means that if we import this before Bcfg2.DBSettings has
        # been populated, Django gets a null configuration, and
        # subsequent updates to Bcfg2.DBSettings won't help.
        import Bcfg2.Reporting.models  # pylint: disable=W0621
        self.reports_entries = (Bcfg2.Reporting.models.Group,
                                Bcfg2.Reporting.models.Bundle,
                                Bcfg2.Reporting.models.FailureEntry,
                                Bcfg2.Reporting.models.ActionEntry,
                                Bcfg2.Reporting.models.PathEntry,
                                Bcfg2.Reporting.models.PackageEntry,
                                Bcfg2.Reporting.models.PathEntry,
                                Bcfg2.Reporting.models.ServiceEntry)
        self.reports_classes = self.reports_entries + (
            Bcfg2.Reporting.models.Client,
            Bcfg2.Reporting.models.Interaction,
            Bcfg2.Reporting.models.Performance)


if HAS_DJANGO:
    class _DjangoProxyCmd(AdminCmd):
        """ Base for admin modes that proxy a command through the
        Django management system """
        command = None
        args = []
        kwargs = {}

        def run(self, _):
            '''Call a django command'''
            if self.command is not None:
                command = self.command
            else:
                command = self.__class__.__name__.lower()
            args = [command] + self.args
            management.call_command(*args, **self.kwargs)

    class DBShell(_DjangoProxyCmd):
        """ Call the Django 'dbshell' command on the database """

    class Shell(_DjangoProxyCmd):
        """ Call the Django 'shell' command on the database """

    class ValidateDB(_DjangoProxyCmd):
        """ Call the Django 'validate' command on the database """
        command = "validate"

    class Syncdb(AdminCmd):
        """ Sync the Django ORM with the configured database """

        def run(self, setup):
            try:
                Bcfg2.DBSettings.sync_databases(
                    interactive=False,
                    verbosity=setup.verbose + setup.debug)
            except ImproperlyConfigured:
                err = sys.exc_info()[1]
                self.logger.error("Django configuration problem: %s" % err)
                raise SystemExit(1)
            except:
                err = sys.exc_info()[1]
                self.logger.error("Database update failed: %s" % err)
                raise SystemExit(1)

    if django.VERSION[0] == 1 and django.VERSION[1] >= 7:
        class Makemigrations(_DjangoProxyCmd):
            """ Call the 'makemigrations' command on the database """
            args = ['Reporting']

    else:
        class Schemamigration(_DjangoProxyCmd):
            """ Call the South 'schemamigration' command on the database """
            args = ['Bcfg2.Reporting']
            kwargs = {'auto': True}


if HAS_REPORTS:
    import datetime

    class ScrubReports(_ReportsCmd):
        """ Perform a thorough scrub and cleanup of the Reporting
        database """

        def setup(self):
            _ReportsCmd.setup(self)
            # this has to be imported after options are parsed,
            # because Django finalizes its settings as soon as it's
            # loaded, which means that if we import this before
            # Bcfg2.DBSettings has been populated, Django gets a null
            # configuration, and subsequent updates to
            # Bcfg2.DBSettings won't help.
            from Bcfg2.Reporting.Compat import transaction
            self.run = transaction.atomic(self.run)

        def run(self, _):  # pylint: disable=E0202
            # Cleanup unused entries
            for cls in self.reports_entries:
                try:
                    start_count = cls.objects.count()
                    cls.prune_orphans()
                    self.logger.info("Pruned %d %s records" %
                                     (start_count - cls.objects.count(),
                                      cls.__name__))
                except:  # pylint: disable=W0702
                    print("Failed to prune %s: %s" %
                          (cls.__name__, sys.exc_info()[1]))

    class InitReports(AdminCmd):
        """ Initialize the Reporting database """
        def run(self, setup):
            verbose = setup.verbose + setup.debug
            try:
                Bcfg2.DBSettings.sync_databases(interactive=False,
                                                verbosity=verbose)
                Bcfg2.DBSettings.migrate_databases(interactive=False,
                                                   verbosity=verbose)
            except:  # pylint: disable=W0702
                self.errExit("%s failed: %s" %
                             (self.__class__.__name__.title(),
                              sys.exc_info()[1]))

    class UpdateReports(InitReports):
        """ Apply updates to the reporting database """

    class ReportsStats(_ReportsCmd):
        """ Print Reporting database statistics """
        def run(self, _):
            for cls in self.reports_classes:
                print("%s has %s records" % (cls.__name__,
                                             cls.objects.count()))

    class PurgeReports(_ReportsCmd):
        """ Purge records from the Reporting database """

        options = AdminCmd.options + [
            Bcfg2.Options.Option("--client", help="Client to operate on"),
            Bcfg2.Options.Option("--days", type=int, metavar='N',
                                 help="Records older than N days"),
            Bcfg2.Options.ExclusiveOptionGroup(
                Bcfg2.Options.BooleanOption("--expired",
                                            help="Expired clients only"),
                Bcfg2.Options.Option("--state", help="Purge entries in state",
                                     choices=['dirty', 'clean', 'modified']),
                required=False)]

        def run(self, setup):
            if setup.days:
                maxdate = datetime.datetime.now() - \
                    datetime.timedelta(days=setup.days)
            else:
                maxdate = None

            starts = {}
            for cls in self.reports_classes:
                starts[cls] = cls.objects.count()
            if setup.expired:
                self.purge_expired(maxdate)
            else:
                self.purge(setup.client, maxdate, setup.state)
            for cls in self.reports_classes:
                self.logger.info("Purged %s %s records" %
                                 (starts[cls] - cls.objects.count(),
                                  cls.__name__))

        def purge(self, client=None, maxdate=None, state=None):
            '''Purge historical data from the database'''
            # indicates whether or not a client should be deleted
            filtered = False

            if not client and not maxdate and not state:
                self.errExit("Refusing to prune all data. Specify an option "
                             "to %s" % self.__class__.__name__.lower())

            ipurge = Bcfg2.Reporting.models.Interaction.objects
            if client:
                try:
                    cobj = Bcfg2.Reporting.models.Client.objects.get(
                        name=client)
                    ipurge = ipurge.filter(client=cobj)
                except Bcfg2.Reporting.models.Client.DoesNotExist:
                    self.errExit("Client %s not in database" % client)
                self.logger.debug("Filtering by client: %s" % client)

            if maxdate:
                filtered = True
                self.logger.debug("Filtering by maxdate: %s" % maxdate)
                ipurge = ipurge.filter(timestamp__lt=maxdate)

            if django.conf.settings.DATABASES['default']['ENGINE'] == \
                    'django.db.backends.sqlite3':
                grp_limit = 100
            else:
                grp_limit = 1000
            if state:
                filtered = True
                self.logger.debug("Filtering by state: %s" % state)
                ipurge = ipurge.filter(state=state)

            count = ipurge.count()
            rnum = 0
            try:
                while rnum < count:
                    grp = list(ipurge[:grp_limit].values("id"))
                    # just in case...
                    if not grp:
                        break
                    Bcfg2.Reporting.models.Interaction.objects.filter(
                        id__in=[x['id'] for x in grp]).delete()
                    rnum += len(grp)
                    self.logger.debug("Deleted %s of %s" % (rnum, count))
            except:  # pylint: disable=W0702
                self.logger.error("Failed to remove interactions: %s" %
                                  sys.exc_info()[1])

            # Prune any orphaned ManyToMany relations
            for m2m in self.reports_entries:
                self.logger.debug("Pruning any orphaned %s objects" %
                                  m2m.__name__)
                m2m.prune_orphans()

            if client and not filtered:
                # Delete the client, ping data is automatic
                try:
                    self.logger.debug("Purging client %s" % client)
                    cobj.delete()
                except:  # pylint: disable=W0702
                    self.logger.error("Failed to delete client %s: %s" %
                                      (client, sys.exc_info()[1]))

        def purge_expired(self, maxdate=None):
            """ Purge expired clients from the Reporting database """

            if maxdate:
                if not isinstance(maxdate, datetime.datetime):
                    raise TypeError("maxdate is not a DateTime object")
                self.logger.debug("Filtering by maxdate: %s" % maxdate)
                clients = Bcfg2.Reporting.models.Client.objects.filter(
                    expiration__lt=maxdate)
            else:
                clients = Bcfg2.Reporting.models.Client.objects.filter(
                    expiration__isnull=False)

            for client in clients:
                self.logger.debug("Purging client %s" % client)
                Bcfg2.Reporting.models.Interaction.objects.filter(
                    client=client).delete()
                client.delete()

    class ReportsSQLAll(_DjangoProxyCmd):
        """ Call the Django 'sqlall' command on the Reporting database """
        args = ["Reporting"]


class Viz(_ServerAdminCmd):
    """ Produce graphviz diagrams of metadata structures """

    options = _ServerAdminCmd.options + [
        Bcfg2.Options.BooleanOption(
            "-H", "--includehosts",
            help="Include hosts in the viz output"),
        Bcfg2.Options.BooleanOption(
            "-b", "--includebundles",
            help="Include bundles in the viz output"),
        Bcfg2.Options.BooleanOption(
            "-k", "--includekey",
            help="Show a key for different digraph shapes"),
        Bcfg2.Options.Option(
            "-c", "--only-client", metavar="<hostname>",
            help="Only show groups and bundles for the named client"),
        Bcfg2.Options.PathOption(
            "-o", "--outfile",
            help="Write viz output to an output file")]

    colors = ['steelblue1', 'chartreuse', 'gold', 'magenta',
              'indianred1', 'limegreen', 'orange1', 'lightblue2',
              'green1', 'blue1', 'yellow1', 'darkturquoise', 'gray66']

    __plugin_blacklist__ = ['DBStats', 'Cfg', 'Pkgmgr', 'Packages', 'Rules',
                            'Decisions', 'Deps', 'Git', 'Svn', 'Fossil', 'Bzr',
                            'Bundler']

    def run(self, setup):
        if setup.outfile:
            fmt = setup.outfile.split('.')[-1]
        else:
            fmt = 'png'

        exc = Executor()
        cmd = ["dot", "-T", fmt]
        if setup.outfile:
            cmd.extend(["-o", setup.outfile])
        inputlist = ["digraph groups {",
                     '\trankdir="LR";',
                     self.metadata.viz(setup.includehosts,
                                       setup.includebundles,
                                       setup.includekey,
                                       setup.only_client,
                                       self.colors)]
        if setup.includekey:
            inputlist.extend(
                ["\tsubgraph cluster_key {",
                 '\tstyle="filled";',
                 '\tcolor="lightblue";',
                 '\tBundle [ shape="septagon" ];',
                 '\tGroup [shape="ellipse"];',
                 '\tGroup Category [shape="trapezium"];\n',
                 '\tProfile [style="bold", shape="ellipse"];',
                 '\tHblock [label="Host1|Host2|Host3",shape="record"];',
                 '\tlabel="Key";',
                 "\t}"])
        inputlist.append("}")
        idata = "\n".join(inputlist)
        try:
            result = exc.run(cmd, inputdata=idata)
        except OSError:
            # on some systems (RHEL 6), you cannot run dot with
            # shell=True.  on others (Gentoo with Python 2.7), you
            # must.  In yet others (RHEL 5), either way works.  I have
            # no idea what the difference is, but it's kind of a PITA.
            result = exc.run(cmd, shell=True, inputdata=idata)
        if not result.success:
            self.errExit("Error running %s: %s" % (cmd, result.error))
        if not setup.outfile:
            print(result.stdout)


class Xcmd(_ProxyAdminCmd):
    """ XML-RPC Command Interface """

    options = _ProxyAdminCmd.options + [
        Bcfg2.Options.PositionalArgument("command"),
        Bcfg2.Options.PositionalArgument("arguments", nargs='*')]

    def run(self, setup):
        try:
            data = getattr(self.proxy, setup.command)(*setup.arguments)
        except Bcfg2.Client.Proxy.ProxyError:
            self.errExit("Proxy Error: %s" % sys.exc_info()[1])

        if data is not None:
            print(data)


class CLI(Bcfg2.Options.CommandRegistry):
    """ CLI class for bcfg2-admin """

    def __init__(self):
        Bcfg2.Options.CommandRegistry.__init__(self)
        self.register_commands(globals().values(), parent=AdminCmd)
        parser = Bcfg2.Options.get_parser(
            description="Manage a running Bcfg2 server",
            components=[self])
        parser.add_options(self.subcommand_options)
        parser.parse()
        if django.VERSION[0] == 1 and django.VERSION[1] >= 7:
            # this has been introduced in django 1.7, so pylint fails with
            # older django releases
            django.setup()  # pylint: disable=E1101

    def run(self):
        """ Run bcfg2-admin """
        try:
            cmd = self.commands[Bcfg2.Options.setup.subcommand]
            if hasattr(cmd, 'setup'):
                cmd.setup()
            return self.runcommand()
        finally:
            self.shutdown()
