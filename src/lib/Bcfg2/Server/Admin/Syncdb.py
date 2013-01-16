import sys
import Bcfg2.settings
import Bcfg2.Options
import Bcfg2.Server.Admin
import Bcfg2.Server.models
from django.core.management import setup_environ, call_command


class Syncdb(Bcfg2.Server.Admin.Mode):
    """ Sync the Django ORM with the configured database """

    def __call__(self, args):
        # Parse options
        setup = Bcfg2.Options.get_option_parser()
        setup.add_option("web_configfile", Bcfg2.Options.WEB_CFILE)
        opts = sys.argv[1:]
        opts.remove(self.__class__.__name__.lower())
        setup.reparse(argv=opts)

        setup_environ(Bcfg2.settings)
        Bcfg2.Server.models.load_models(cfile=setup['web_configfile'])

        try:
            call_command("syncdb", interactive=False, verbosity=0)
            self._database_available = True
        except ImproperlyConfigured:
            err = sys.exc_info()[1]
            self.log.error("Django configuration problem: %s" % err)
            raise SystemExit(1)
        except:
            err = sys.exc_info()[1]
            self.log.error("Database update failed: %s" % err)
            raise SystemExit(1)
