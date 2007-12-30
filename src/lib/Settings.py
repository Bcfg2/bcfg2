"""
Settings for bcfg2.
FIXME: simplify code!
FIXME: add statistics configuration
"""

__revision__ = '$Revision$'

import logging, socket, ConfigParser

class Settings(object):

    def __init__(self):
        self.CONFIG_FILE             = self.default_config_file()

        self.SERVER_GENERATORS       = self.default_server_generators()
        self.SERVER_REPOSITORY       = self.default_server_repository()
        self.SERVER_STRUCTURES       = self.default_server_structures()
        self.SERVER_SVN              = self.default_server_svn()

        self.COMMUNICATION_KEY       = self.default_communication_key()
        self.COMMUNICATION_PASSWORD  = self.default_communication_password()
        self.COMMUNICATION_PROTOCOL  = self.default_communication_protocol()
        self.COMMUNICATION_USER      = self.default_communication_user()

        self.COMPONENTS_BCFG2        = self.default_components_bcfg2()
        self.COMPONENTS_BCFG2_STATIC = self.default_components_bcfg2_static()


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
        # communication config
        if cfp.has_section('communication'):
            try:
                self.COMMUNICATION_PROTOCOL = cfp.get('communication','protocol')
            except:
              pass
            try:
                self.COMMUNICATION_PASSWORD = cfp.get('communication','password')
            except:
              pass
            try:
                self.COMMUNICATION_KEY      = cfp.get('communication','key')
            except:
              pass
            try:
                self.COMMUNICATION_USER     = cfp.get('communication','user')
            except:
              pass
        # components config
        if cfp.has_section('components'):
            try:
                self.COMPONENTS_BCFG2 = cfp.get('components', 'bcfg2')
                self.COMPONENTS_BCFG2_STATIC = True
            except:
                pass
        # server config
        if cfp.has_section('server'):
            try:
                self.SERVER_GENERATORS = cfp.get('server','generators').replace(' ','').split(',')
            except:
              pass
            try:
                self.SERVER_REPOSITORY = cfp.get('server','repository')
            except:
              pass
            try:
                self.SERVER_STRUCTURES = cfp.get('server','structures').replace(' ','').split(',')
            except:
              pass
            try:
                self.SERVER_SVN        = cfp.get('server','svn')
            except:
              pass

        return

    def default_config_file(self):
        return '/etc/bcfg2.conf'

    def default_server_generators(self):
        return ['SSHbase', 'Cfg', 'Pkgmgr', 'Rules']

    def default_server_structures(self):
        return ['Bundler', 'Base']

    def default_server_repository(self):
        return '/var/lib/bcfg2/'

    def default_communication_key(self):
        return False

    def default_communication_password(self):
        return 'password'

    def default_communication_protocol(self):
        return 'xmlrpc/ssl'

    def default_communication_user(self):
        return 'root'

    def default_components_bcfg2(self):
        return (socket.gethostname(), 0)

    def default_components_bcfg2_static(self):
        return False

    def default_sendmail_path(self):
        return '/usr/sbin/sendmail'

    def default_server_svn(self):
        return None



settings = Settings()
