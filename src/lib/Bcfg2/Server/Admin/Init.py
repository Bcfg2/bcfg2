""" Interactively initialize a new repository. """

import os
import sys
import stat
import select
import random
import socket
import string
import getpass
import subprocess

import Bcfg2.Server.Admin
import Bcfg2.Server.Plugin
import Bcfg2.Options
import Bcfg2.Server.Plugins.Metadata
from Bcfg2.Compat import input  # pylint: disable=W0622

# default config file
CONFIG = '''[server]
repository = %s
plugins = %s

[statistics]
sendmailpath = %s
#web_debug = False
#time_zone =

[database]
#engine = sqlite3
# 'postgresql', 'mysql', 'mysql_old', 'sqlite3' or 'ado_mssql'.
#name =
# Or path to database file if using sqlite3.
#<repository>/bcfg2.sqlite is default path if left empty
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
protocol = %s
password = %s
certificate = %s
key = %s
ca = %s

[components]
bcfg2 = %s
'''

# Default groups
GROUPS = '''<Groups version='3.0'>
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
   <Group name='arch'/>
</Groups>
'''

# Default contents of clients.xml
CLIENTS = '''<Clients version="3.0">
   <Client profile="basic" name="%s"/>
</Clients>
'''

# Mapping of operating system names to groups
OS_LIST = [('Red Hat/Fedora/RHEL/RHAS/Centos', 'redhat'),
           ('SUSE/SLES', 'suse'),
           ('Mandrake', 'mandrake'),
           ('Debian', 'debian'),
           ('Ubuntu', 'ubuntu'),
           ('Gentoo', 'gentoo'),
           ('FreeBSD', 'freebsd'),
           ('Arch', 'arch')]


def safe_input(prompt):
    """ input() that flushes the input buffer before accepting input """
    # flush input buffer
    while len(select.select([sys.stdin.fileno()], [], [], 0.0)[0]) > 0:
        os.read(sys.stdin.fileno(), 4096)
    return input(prompt)


def gen_password(length):
    """Generates a random alphanumeric password with length characters."""
    chars = string.letters + string.digits
    return "".join(random.choice(chars) for i in range(length))


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


def create_conf(confpath, confdata):
    """ create the config file """
    # Don't overwrite existing bcfg2.conf file
    if os.path.exists(confpath):
        result = safe_input("\nWarning: %s already exists. "
                            "Overwrite? [y/N]: " % confpath)
        if result not in ['Y', 'y']:
            print("Leaving %s unchanged" % confpath)
            return
    try:
        open(confpath, "w").write(confdata)
        os.chmod(confpath, stat.S_IRUSR | stat.S_IWUSR)  # 0600
    except Exception:
        err = sys.exc_info()[1]
        print("Error trying to write configuration file '%s': %s" %
              (confpath, err))
        raise SystemExit(1)


class Init(Bcfg2.Server.Admin.Mode):
    """Interactively initialize a new repository."""
    options = {'configfile': Bcfg2.Options.CFILE,
               'plugins': Bcfg2.Options.SERVER_PLUGINS,
               'proto': Bcfg2.Options.SERVER_PROTOCOL,
               'repo': Bcfg2.Options.SERVER_REPOSITORY,
               'sendmail': Bcfg2.Options.SENDMAIL_PATH}

    def __init__(self, setup):
        Bcfg2.Server.Admin.Mode.__init__(self, setup)
        self.data = dict()
        self.plugins = Bcfg2.Options.SERVER_PLUGINS.default

    def _set_defaults(self, opts):
        """Set default parameters."""
        self.data['configfile'] = opts['configfile']
        self.data['repopath'] = opts['repo']
        self.data['password'] = gen_password(8)
        self.data['server_uri'] = "https://%s:6789" % socket.getfqdn()
        self.data['sendmail'] = opts['sendmail']
        self.data['proto'] = opts['proto']
        if os.path.exists("/etc/pki/tls"):
            self.data['keypath'] = "/etc/pki/tls/private/bcfg2.key"
            self.data['certpath'] = "/etc/pki/tls/certs/bcfg2.crt"
        elif os.path.exists("/etc/ssl"):
            self.data['keypath'] = "/etc/ssl/bcfg2.key"
            self.data['certpath'] = "/etc/ssl/bcfg2.crt"
        else:
            basepath = os.path.dirname(self.configfile)
            self.data['keypath'] = os.path.join(basepath, "bcfg2.key")
            self.data['certpath'] = os.path.join(basepath, 'bcfg2.crt')

    def __call__(self, args):
        # Parse options
        opts = Bcfg2.Options.OptionParser(self.options)
        opts.parse(args)
        self._set_defaults(opts)

        # Prompt the user for input
        self._prompt_config()
        self._prompt_repopath()
        self._prompt_password()
        self._prompt_hostname()
        self._prompt_server()
        self._prompt_groups()
        self._prompt_keypath()
        self._prompt_certificate()

        # Initialize the repository
        self.init_repo()

    def _prompt_hostname(self):
        """Ask for the server hostname."""
        data = safe_input("What is the server's hostname [%s]: " %
                          socket.getfqdn())
        if data != '':
            self.data['shostname'] = data
        else:
            self.data['shostname'] = socket.getfqdn()

    def _prompt_config(self):
        """Ask for the configuration file path."""
        newconfig = safe_input("Store Bcfg2 configuration in [%s]: " %
                               self.configfile)
        if newconfig != '':
            self.data['configfile'] = os.path.abspath(newconfig)

    def _prompt_repopath(self):
        """Ask for the repository path."""
        while True:
            newrepo = safe_input("Location of Bcfg2 repository [%s]: " %
                                 self.data['repopath'])
            if newrepo != '':
                self.data['repopath'] = os.path.abspath(newrepo)
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
            "(without echoing; leave blank for a random): ").strip()
        if len(newpassword) != 0:
            self.data['password'] = newpassword

    def _prompt_server(self):
        """Ask for the server name."""
        newserver = safe_input("Input the server location [%s]: " %
                               self.data['server_uri'])
        if newserver != '':
            self.data['server_uri'] = newserver

    def _prompt_groups(self):
        """Create the groups.xml file."""
        prompt = '''Input base Operating System for clients:\n'''
        for entry in OS_LIST:
            prompt += "%d: %s\n" % (OS_LIST.index(entry) + 1, entry[0])
        prompt += ': '
        while True:
            try:
                osidx = int(safe_input(prompt))
                self.data['os_sel'] = OS_LIST[osidx - 1][1]
                break
            except ValueError:
                continue

    def _prompt_certificate(self):
        """Ask for the key details (country, state, and location)."""
        print("The following questions affect SSL certificate generation.")
        print("If no data is provided, the default values are used.")
        newcountry = safe_input("Country name (2 letter code) for "
                                "certificate: ")
        if newcountry != '':
            if len(newcountry) == 2:
                self.data['country'] = newcountry
            else:
                while len(newcountry) != 2:
                    newcountry = safe_input("2 letter country code (eg. US): ")
                    if len(newcountry) == 2:
                        self.data['country'] = newcountry
                        break
        else:
            self.data['country'] = 'US'

        newstate = safe_input("State or Province Name (full name) for "
                              "certificate: ")
        if newstate != '':
            self.data['state'] = newstate
        else:
            self.data['state'] = 'Illinois'

        newlocation = safe_input("Locality Name (eg, city) for certificate: ")
        if newlocation != '':
            self.data['location'] = newlocation
        else:
            self.data['location'] = 'Argonne'

    def _prompt_keypath(self):
        """ Ask for the key pair location.  Try to use sensible
        defaults depending on the OS """
        keypath = safe_input("Path where Bcfg2 server private key will be "
                             "created [%s]: " % self.data['keypath'])
        if keypath:
            self.data['keypath'] = keypath
        certpath = safe_input("Path where Bcfg2 server cert will be created "
                              "[%s]: " % self.data['certpath'])
        if certpath:
            self.data['certpath'] = certpath

    def _init_plugins(self):
        """Initialize each plugin-specific portion of the repository."""
        for plugin in self.plugins:
            if plugin == 'Metadata':
                Bcfg2.Server.Plugins.Metadata.Metadata.init_repo(
                    self.data['repopath'],
                    groups_xml=GROUPS % self.data['os_sel'],
                    clients_xml=CLIENTS % socket.getfqdn())
            else:
                try:
                    module = __import__("Bcfg2.Server.Plugins.%s" % plugin, '',
                                        '', ["Bcfg2.Server.Plugins"])
                    cls = getattr(module, plugin)
                    cls.init_repo(self.data['repopath'])
                except:  # pylint: disable=W0702
                    err = sys.exc_info()[1]
                    print("Plugin setup for %s failed: %s\n"
                          "Check that dependencies are installed" % (plugin,
                                                                     err))

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

        confdata = CONFIG % (self.data['repopath'],
                             ','.join(self.plugins),
                             self.data['sendmail'],
                             self.data['proto'],
                             self.data['password'],
                             self.data['certpath'],
                             self.data['keypath'],
                             self.data['certpath'],
                             self.data['server_uri'])

        # Create the configuration file and SSL key
        create_conf(self.data['configfile'], confdata)
        create_key(self.data['shostname'], self.data['keypath'],
                   self.data['certpath'], self.data['country'],
                   self.data['state'], self.data['location'])
