import os, socket
import Bcfg2.Server.Admin
import Bcfg2.Options

config = '''
[server]
repository = %s
structures = %s
generators = %s

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
key = %s/bcfg2.key

[components]
bcfg2 = %s
'''

groups = '''
<Groups version='3.0'>
   <Group profile='true' public='false' default='true' name='basic'>
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
clients = '''
<Clients version="3.0">
   <Client profile="basic" pingable="Y" pingtime="0" name="%s"/>
</Clients>
'''

os_list = [('Redhat/Fedora/RHEL/RHAS/Centos', 'redhat'),
           ('SUSE/SLES', 'suse'),
           ('Mandrake', 'mandrake'),
           ('Debian', 'debian'),
           ('Ubuntu', 'ubuntu'),
           ('Gentoo', 'gentoo'),
           ('FreeBSD', 'freebsd')]


class Init(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = 'bcfg2-admin init'
    __longhelp__ = __shorthelp__ + '\n\tCompare two client specifications or directories of specifications'
    options = {'repo': Bcfg2.Options.SERVER_REPOSITORY,
               'struct': Bcfg2.Options.SERVER_STRUCTURES,
               'gens': Bcfg2.Options.SERVER_GENERATORS,
               'proto': Bcfg2.Options.SERVER_PROTOCOL,
               'sendmail': Bcfg2.Options.SENDMAIL_PATH,
               'configfile': Bcfg2.Options.CFILE}
    
    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        opts = Bcfg2.Options.OptionParser(self.options)
        opts.parse([])
        repopath = raw_input("location of bcfg2 repository [%s]: " % opts['repo'])
        if repopath == '':
            repopath = opts['repo']
        password = ''
        while ( password == '' ):
            password = raw_input(
                "Input password used for communication verification: " )
        server = "https://%s:6789" % socket.getfqdn()
        rs = raw_input( "Input the server location [%s]: " % server)
        if rs:
            server = rs
        #create the groups.xml file
        prompt = '''Input base Operating System for clients:\n'''
        for entry in os_list:
            prompt += "%d: \n" % (os_list.index(entry) + 1, entry[0])
        prompt += ': '
        os_sel = os_list[int(raw_input(prompt))-1][1]
        self.initializeRepo(repopath, server, password, os_sel, opts)
        print "Repository created successfuly in %s" % (repopath)

    def initializeRepo(self, repo, server_uri, password, os_selection, opts):
        '''Setup a new repo'''
        keypath = os.path.dirname(os.path.abspath(opts['configfile']))
        confdata = config % ( 
                        repo, opts['struct'], opts['gens'], 
                        opts['sendmail'], opts['proto'],
                        password, keypath, server_uri 
                    )

        open(opts['configfile'], "w").write(confdata)
        # FIXME automate ssl key generation
        os.popen('openssl req -x509 -nodes -days 1000 -newkey rsa:1024 -out %s/bcfg2.key -keyout %s/bcfg2.key' % (keypath, keypath))
        try:
            os.chmod('%s/bcfg2.key'% keypath,'0600')
        except:
            pass
    
        for subdir in ['SSHbase', 'Cfg', 'Pkgmgr', 'Rules', 'etc', 'Metadata',
                       'Base', 'Bundler']:
            path = "%s/%s" % (repo, subdir)
            newpath = ''
            for subdir in path.split('/'):
                newpath = newpath + subdir + '/'
                try:
                    os.mkdir(newpath)
                except:
                    continue
            
        open("%s/Metadata/groups.xml"%repo, "w").write(groups % os_selection)
        #now the clients file
        open("%s/Metadata/clients.xml"%repo, "w").write(clients % socket.getfqdn())


