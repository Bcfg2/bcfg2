"""
Settings for bcfg2.
FIXME: simplify code!
FIXME: add statistics configuration
"""

__revision__ = '$Revision$'

import logging, socket, ConfigParser

locations = {'communication': [('COMMUNICATION_PROTOCOL', 'protocol'),
                               ('COMMUNICATION_PASSWORD', 'communication'),
                               ('COMMUNICATION_KEY', 'key'),
                               ('COMMUNICATION_USER', 'user')],
             'server': [('SERVER_PREFIX', 'prefix'),
                        ('SERVER_GENERATORS','generators'),
                        ('SERVER_REPOSITORY', 'repository'),
                        ('SERVER_STRUCTURES','structures'),                        
                        ('SERVER_SVN', 'svn')],
             'components': [('COMPONENTS_BCFG2', 'bcfg2'),
                            ('COMPONENTS_BCFG2_STATIC', 'bcfg2')],
             'statistics': [('SENDMAIL_PATH', 'sendmai;')]}

cookers = {'COMPONENTS_BCFG2_STATIC': lambda x:True,
           'SERVER_GENERATORS': lambda x:x.replace(' ','').split(','),
           'SERVER_STRUCTURES': lambda x:x.replace(' ','').split(',')}

class Settings(object):

    def __init__(self):
        self.CONFIG_FILE             = '/etc/bcfg2.conf'
        
        self.SERVER_GENERATORS       = ['SSHbase', 'Cfg', 'Pkgmgr', 'Rules']
        self.SERVER_PREFIX           = '/usr'
        self.SERVER_REPOSITORY       = '/var/lib/bcfg2'
        self.SERVER_STRUCTURES       = ['Bundler', 'Base']
        self.SERVER_SVN              = False

        self.COMMUNICATION_KEY       = False
        self.COMMUNICATION_PASSWORD  = 'password'
        self.COMMUNICATION_PROTOCOL  = 'xmlrpc/ssl'
        self.COMMUNICATION_USER      = 'root'

        self.COMPONENTS_BCFG2        = (socket.gethostname(), 0)
        self.COMPONENTS_BCFG2_STATIC = False

        self.SENDMAIL_PATH           = '/usr/sbin/sendmail'

    def __getattr__(self, name):
        print "name = %s\n" % name
        if name == '__members__':
            return self.name()
        return getattr(self, name)

    def read_config_file(self, filename):

        logger = logging.getLogger('bcfg2 settings')

        # set config file
        if not filename:
          logger.info("No config file given. Trying default config file '%s'." % self.CONFIG_FILE)
        else:
          logger.debug("Trying user specified config file '%s'." % filename)
          self.CONFIG_FILE = filename

        # open config file
        try:
            cf = open(self.CONFIG_FILE)
        except IOError:
            logger.info("Skipping not accessable config file '%s'." % self.CONFIG_FILE)
            return

        # parse config file
        cfp = ConfigParser.ConfigParser()
        try:
            cfp.readfp(cf)
        except Exception, e:
          logger.error("Content of config file '%s' is not valid. Correct it!\n%s\n" % (self.CONFIG_FILE, e))
          raise SystemExit, 1
      
        for section in locations:
            if cfp.has_section(section):
                for key, location in locations[section]:
                    try:
                        if key in cookers:
                              setattr(self, key, cookers[key](cfp.get(section,
                                                                      location)))
                        else:
                              setattr(self, key, cfp.get(section, location))
                    except:
                        pass

settings = Settings()
