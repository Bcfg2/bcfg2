import getpass
import os
import random
import socket
import string
import subprocess
import Bcfg2.Server.Admin
import Bcfg2.Server.Plugin
import Bcfg2.Options

from Bcfg2.Server.Plugins import (Account, Base, Bundler, Cfg,  
                                  Decisions, Deps, Metadata, 
                                  Packages,  Pkgmgr, Probes, 
                                  Properties, Rules, Snapshots, 
                                  SSHbase, Svcmgr, TCheetah, 
                                  TGenshi)

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
certificate = %s/bcfg2.key
key = %s/bcfg2.key

[components]
bcfg2 = %s
'''

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

clients = '''<Clients version="3.0">
   <Client profile="basic" pingable="Y" pingtime="0" name="%s"/>
</Clients>
'''

os_list = [
           ('Redhat/Fedora/RHEL/RHAS/Centos',   'redhat'),
           ('SUSE/SLES',                        'suse'),
           ('Mandrake',                         'mandrake'),
           ('Debian',                           'debian'),
           ('Ubuntu',                           'ubuntu'),
           ('Gentoo',                           'gentoo'),
           ('FreeBSD',                          'freebsd')
          ]


class Init(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = ("Interactively initialize a new repository")
    __longhelp__ = __shorthelp__ + "\n\nbcfg2-admin init"
    __usage__ = "bcfg2-admin init"
    options = {
                'configfile': Bcfg2.Options.CFILE,
                'plugins'   : Bcfg2.Options.SERVER_PLUGINS,
                'proto'     : Bcfg2.Options.SERVER_PROTOCOL,
                'repo'      : Bcfg2.Options.SERVER_REPOSITORY,
                'sendmail'  : Bcfg2.Options.SENDMAIL_PATH,
              }
    repopath = ""
    response = ""
    
    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        opts = Bcfg2.Options.OptionParser(self.options)
        opts.parse([])

        configfile = raw_input("Store bcfg2 configuration in [%s]: " %
                                opts['configfile'])
        if configfile == '':
            configfile = opts['configfile']

        self.repopath = raw_input("Location of bcfg2 repository [%s]: " %
                              opts['repo'])
        if self.repopath == '':
            self.repopath = opts['repo']
        if os.path.isdir(self.repopath):
            self.response = raw_input("Directory %s exists. Overwrite? [Y/n]:"\
                                  % self.repopath)
        
        password = getpass.getpass(
                "Input password used for communication verification "
                "(without echoing; leave blank for a random): ")
        if len(password.strip()) == 0:
            password = self.genPassword()
        
        server = "https://%s:6789" % socket.getfqdn()
        rs = raw_input( "Input the server location [%s]: " % server)
        if rs:
            server = rs

        # create the groups.xml file
        prompt = '''Input base Operating System for clients:\n'''
        for entry in os_list:
            prompt += "%d: %s\n" % (os_list.index(entry) + 1, entry[0])
        prompt += ': '
        os_sel = os_list[int(raw_input(prompt))-1][1]
        self.initializeRepo(configfile, self.repopath, server,
                            password, os_sel, opts)

    def genPassword(self):
        chars = string.letters + string.digits
        newpasswd = ''
        for i in range(8):
            newpasswd = newpasswd + random.choice(chars)
        return newpasswd

    def initializeRepo(self, configfile, repo, server_uri,
                       password, os_selection, opts):
        '''Setup a new repo'''
        keypath = os.path.dirname(os.path.abspath(configfile))

        confdata = config % ( 
                        repo, ','.join(opts['plugins']),
                        opts['sendmail'], opts['proto'],
                        password, keypath, keypath, server_uri 
                    )

        # don't overwrite existing bcfg2.conf file
        if os.path.exists(configfile):
            print("\nWarning: %s already exists. Will not be "
                  "overwritten...\n" % configfile)
        else:
            try:
                open(configfile, "w").write(confdata)
                os.chmod(configfile, 0600)
            except Exception, e:
                print("Error %s occured while trying to write configuration "
                      "file to '%s'\n" %
                       (e, configfile))

        # FIXME automate ssl key generation
        # FIXME key generation may fail as non-root user
        subprocess.call(("openssl " \
                         "req -x509 -nodes -days 1000 -newkey rsa:1024 " \
                         "-out %s/bcfg2.key -keyout %s/bcfg2.key" % \
                         (keypath, keypath)), shell=True)
        try:
            os.chmod('%s/bcfg2.key'% keypath, 0600)
        except:
            pass
    
        # Overwrite existing directory/repo?
        if self.response == "n":
            print "Kept old repository in %s" % (self.repopath)
            return
        else:
            # FIXME repo creation may fail as non-root user
            plug_list = ['Account', 'Base', 'Bundler', 'Cfg', 
                         'Decisions', 'Deps', 'Metadata', 'Packages', 
                         'Pkgmgr', 'Probes', 'Properties', 'Rules', 
                         'Snapshots', 'SSHbase', 'Statistics', 'Svcmgr', 
                         'TCheetah', 'TGenshi']
            default_repo = ['SSHbase', 'Cfg', 'Pkgmgr', 'Rules', 
                            'Metadata', 'Base', 'Bundler']
            plugins = []
            print 'Repository configuration, choose plugins:'
            default = raw_input("Use default plugins? [Y/n]: ").lower()
            if default == 'y' or default == '':
                plugins = default_repo
            else:
                while True:
                    plugins_are_valid = True
                    plug_str = raw_input("Specify plugins: ")
                    plugins = plug_str.split(',')
                    for plugin in plugins:
                        plugin = plugin.strip()
                        if not plugin in plug_list:
                            plugins_are_valid = False
                            print "ERROR: plugin %s not recognized" % plugin
                    if plugins_are_valid:
                        break
                
            path = "%s/%s" % (repo, 'etc')                              
            newpath = ''                                                 
            for subdir in path.split('/'):                               
                newpath = newpath + subdir + '/'                         
                try:                                                     
                    os.mkdir(newpath)                                    
                except:                                                  
                    continue

            for plugin in plugins:
                if plugin == 'Metadata':
                    Bcfg2.Server.Plugins.Metadata.Metadata.init_repo(repo, groups, os_selection, clients)
                else:
                    try:
                        getattr(getattr(getattr(Bcfg2.Server.Plugins, plugin), plugin), 'init_repo')(repo)
                    except:
                        print 'Plugin setup for %s failed. Check that dependencies are installed?' % plugin
            
            print "Repository created successfuly in %s" % (self.repopath)
