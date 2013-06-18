import sys
import Bcfg2.settings
import Bcfg2.Options
import Bcfg2.Server.Admin
import Bcfg2.Server.models
from django.core.exceptions import ImproperlyConfigured
from django.core.management import setup_environ, call_command


class Syncdb(Bcfg2.Server.Admin.Mode):
    """ Sync the Django ORM with the configured database """
    options = {'configfile': Bcfg2.Options.WEB_CFILE}

    def __call__(self, args):
        # Parse options
        opts = Bcfg2.Options.OptionParser(self.options)
        opts.parse(args)

        setup_environ(Bcfg2.settings)
        Bcfg2.Server.models.load_models(cfile=opts['configfile'])

        try:
            call_command("syncdb", interactive=False, verbosity=0)
            self._database_available = True
        except ImproperlyConfigured:
            self.errExit("Django configuration problem: %s" %
                         sys.exc_info()[1])
        except:
            self.errExit("Database update failed: %s" % sys.exc_info()[1])
