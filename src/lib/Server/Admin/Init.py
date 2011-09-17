import getpass
import os
import random
import socket
import stat
import string
import sys
import subprocess
import Bcfg2.Server.Admin
import Bcfg2.Server.Plugin
import Bcfg2.Options

# default config file
config = '''
[server]
repository = %s
plugins = %s

[statistics]
sendmailpath = %s
database_engine = sqlite3
# 'postgresql', 'mysql', 'mysql_old', 'sqlite3' or 'ado_mssql'.
database_name =
# Or path to database file if using sqlite3.
#<repository>/etc/brpt.sqlite is default path if left empty
database_user =
# Not used with sqlite3.
database_password =
# Not used with sqlite3.
database_host =
# Not used with sqlite3.
database_port =
# Set to empty string for default. Not used with sqlite3.
web_debug = True

[communication]
protocol = %s
password = %s
certificate = %s
key = %s
ca = %s

[components]
bcfg2 = %s
'''

# Default groups
groups = '''<Groups version='3.0'>
   <Group profile='true' public='true' default='true' name='basic'>
      <Group name='%s'/>
   </Group>
   <Group name='ubuntu'/>
   <Group name='debian'/>
   <Group name='freebsd'/>
   <Group name='gentoo'/>
   <Group name='redhat'/>
   <Group name='suse'/>
   <Group name='mandrake'/>
   <Group name='solaris'/>
</Groups>
'''

# Default contents of clients.xml
clients = '''<Clients version="3.0">
   <Client profile="basic" pingable="Y" pingtime="0" name="%s"/>
</Clients>
'''

# Mapping of operating system names to groups
os_list = [('Red Hat/Fedora/RHEL/RHAS/Centos', 'redhat'),
           ('SUSE/SLES', 'suse'),
           ('Mandrake', 'mandrake'),
           ('Debian', 'debian'),
           ('Ubuntu', 'ubuntu'),
           ('Gentoo', 'gentoo'),
           ('FreeBSD', 'freebsd')]

# Complete list of plugins
plugin_list = ['Account',
               'Base',
               'Bundler',
               'Bzr',
               'Cfg',
               'Decisions',
               'Deps',
               'Git',
               'Guppy',
               'Hg',
               'Metadata',
               'NagiosGen',
               'Ohai',
               'Packages',
               'Pkgmgr',
               'Probes',
               'Properties',
               'Rules',
               'Snapshots',
               'SSHbase',
               'SSLCA',
               'Statistics',
               'Svcmgr',
               'TCheetah',
               'TGenshi']

# Default list of plugins to use
default_plugins = Bcfg2.Options.SERVER_PLUGINS.default


def get_input(prompt):
    """py3k compatible function to get input"""
    try:
        return raw_input(prompt)
    except NameError:
        return input(prompt)


def gen_password(length):
    """Generates a random alphanumeric password with length characters."""
    chars = string.letters + string.digits
    newpasswd = ''
    for i in range(length):
        newpasswd = newpasswd + random.choice(chars)
    return newpasswd


def create_key(hostname, keypath, certpath, country, state, location):
    """Creates a bcfg2.key at the directory specifed by keypath."""
    kcstr = ("openssl req -batch -x509 -nodes -subj '/C=%s/ST=%s/L=%s/CN=%s' "
             "-days 1000 -newkey rsa:2048 -keyout %s -noout" % (country,
                                                                state,
                                                                location,
                                                                hostname,
                                                                keypath))
    subprocess.call((kcstr), shell=True)
    ccstr = ("openssl req -batch -new  -subj '/C=%s/ST=%s/L=%s/CN=%s' -key %s "
             "| openssl x509 -req -days 1000 -signkey %s -out %s" % (country,
                                                                     state,
                                                                     location,
                                                                     hostname,
                                                                     keypath,
                                                                     keypath,
                                                                     certpath))
    subprocess.call((ccstr), shell=True)
    os.chmod(keypath, stat.S_IRUSR | stat.S_IWUSR)  # 0600


def create_conf(confpath, confdata, keypath):
    # Don't overwrite existing bcfg2.conf file
    if os.path.exists(confpath):
        result = get_input("\nWarning: %s already exists. "
                           "Overwrite? [y/N]: " % confpath)
        if result not in ['Y', 'y']:
            print("Leaving %s unchanged" % confpath)
            return
    try:
        open(confpath, "w").write(confdata)
        os.chmod(confpath, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except Exception:
        e = sys.exc_info()[1]
        print("Error %s occured while trying to write configuration "
              "file to '%s'.\n" %
               (e, confpath))
        raise SystemExit(1)


class Init(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = ("Interactively initialize a new repository.")
    __longhelp__ = __shorthelp__ + "\n\nbcfg2-admin init"
    __usage__ = "bcfg2-admin init"
    options = {'configfile': Bcfg2.Options.CFILE,
               'plugins': Bcfg2.Options.SERVER_PLUGINS,
               'proto': Bcfg2.Options.SERVER_PROTOCOL,
               'repo': Bcfg2.Options.SERVER_REPOSITORY,
               'sendmail': Bcfg2.Options.SENDMAIL_PATH}
    repopath = ""
    response = ""

    def __init__(self, configfile):
        Bcfg2.Server.Admin.Mode.__init__(self, configfile)

    def _set_defaults(self):
        """Set default parameters."""
        self.configfile = self.opts['configfile']
        self.repopath = self.opts['repo']
        self.password = gen_password(8)
        self.server_uri = "https://%s:6789" % socket.getfqdn()
        self.plugins = default_plugins

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)

        # Parse options
        self.opts = Bcfg2.Options.OptionParser(self.options)
        self.opts.parse(args)
        self._set_defaults()

        # Prompt the user for input
        self._prompt_config()
        self._prompt_repopath()
        self._prompt_password()
        self._prompt_hostname()
        self._prompt_server()
        self._prompt_groups()
        # self._prompt_plugins()
        self._prompt_certificate()

        # Initialize the repository
        self.init_repo()

    def _prompt_hostname(self):
        """Ask for the server hostname."""
        data = get_input("What is the server's hostname [%s]: " %
                            socket.getfqdn())
        if data != '':
            self.shostname = data
        else:
            self.shostname = socket.getfqdn()

    def _prompt_config(self):
        """Ask for the configuration file path."""
        newconfig = get_input("Store Bcfg2 configuration in [%s]: " %
                                self.configfile)
        if newconfig != '':
            self.configfile = os.path.abspath(newconfig)

    def _prompt_repopath(self):
        """Ask for the repository path."""
        while True:
            newrepo = get_input("Location of Bcfg2 repository [%s]: " %
                                    self.repopath)
            if newrepo != '':
                self.repopath = os.path.abspath(newrepo)
            if os.path.isdir(self.repopath):
                response = get_input("Directory %s exists. Overwrite? [y/N]:" \
                                        % self.repopath)
                if response.lower().strip() == 'y':
                    break
            else:
                break

    def _prompt_password(self):
        """Ask for a password or generate one if none is provided."""
        newpassword = getpass.getpass(
                "Input password used for communication verification "
                "(without echoing; leave blank for a random): ").strip()
        if len(newpassword) != 0:
            self.password = newpassword

    def _prompt_server(self):
        """Ask for the server name."""
        newserver = get_input("Input the server location [%s]: " %
                                self.server_uri)
        if newserver != '':
            self.server_uri = newserver

    def _prompt_groups(self):
        """Create the groups.xml file."""
        prompt = '''Input base Operating System for clients:\n'''
        for entry in os_list:
            prompt += "%d: %s\n" % (os_list.index(entry) + 1, entry[0])
        prompt += ': '
        while True:
            try:
                osidx = int(get_input(prompt))
                self.os_sel = os_list[osidx - 1][1]
                break
            except ValueError:
                continue

    def _prompt_plugins(self):
        default = get_input("Use default plugins? (%s) [Y/n]: " %
                            ''.join(default_plugins)).lower()
        if default != 'y' or default != '':
            while True:
                plugins_are_valid = True
                plug_str = get_input("Specify plugins: ")
                plugins = plug_str.split(',')
                for plugin in plugins:
                    plugin = plugin.strip()
                    if not plugin in plugin_list:
                        plugins_are_valid = False
                        print("ERROR: Plugin %s not recognized" % plugin)
                if plugins_are_valid:
                    break

    def _prompt_certificate(self):
        """Ask for the key details (country, state, and location)."""
        print("The following questions affect SSL certificate generation.")
        print("If no data is provided, the default values are used.")
        newcountry = get_input("Country name (2 letter code) for certificate: ")
        if newcountry != '':
            if len(newcountry) == 2:
                self.country = newcountry
            else:
                while len(newcountry) != 2:
                    newcountry = get_input("2 letter country code (eg. US): ")
                    if len(newcountry) == 2:
                        self.country = newcountry
                        break
        else:
            self.country = 'US'

        newstate = get_input("State or Province Name (full name) for certificate: ")
        if newstate != '':
            self.state = newstate
        else:
            self.state = 'Illinois'

        newlocation = get_input("Locality Name (eg, city) for certificate: ")
        if newlocation != '':
            self.location = newlocation
        else:
            self.location = 'Argonne'

    def _init_plugins(self):
        """Initialize each plugin-specific portion of the repository."""
        for plugin in self.plugins:
            if plugin == 'Metadata':
                Bcfg2.Server.Plugins.Metadata.Metadata.init_repo(self.repopath,
                                                                 groups,
                                                                 self.os_sel,
                                                                 clients)
            else:
                try:
                    module = __import__("Bcfg2.Server.Plugins.%s" % plugin, '',
                                        '', ["Bcfg2.Server.Plugins"])
                    cls = getattr(module, plugin)
                    cls.init_repo(self.repopath)
                except Exception:
                    e = sys.exc_info()[1]
                    print("Plugin setup for %s failed: %s\n"
                          "Check that dependencies are installed?" % (plugin, e))

    def init_repo(self):
        """Setup a new repo and create the content of the configuration file."""
        keypath = os.path.dirname(self.configfile)
        kpath = os.path.join(keypath, 'bcfg2.key')
        cpath = os.path.join(keypath, 'bcfg2.crt')

        confdata = config % (self.repopath,
                             ','.join(self.plugins),
                             self.opts['sendmail'],
                             self.opts['proto'],
                             self.password,
                             cpath,
                             kpath,
                             cpath,
                             self.server_uri)

        # Create the configuration file and SSL key
        create_conf(self.configfile, confdata, keypath)
        create_key(self.shostname, kpath, cpath, self.country,
                   self.state, self.location)

        # Create the repository
        path = os.path.join(self.repopath, 'etc')
        try:
            os.makedirs(path)
            self._init_plugins()
            print("Repository created successfuly in %s" % (self.repopath))
        except OSError:
            print("Failed to create %s." % path)
