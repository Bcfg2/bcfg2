import Bcfg2.settings
import Bcfg2.Options
import Bcfg2.Server.Admin
import Bcfg2.Server.models
from django.core.management import setup_environ, call_command


class Syncdb(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = ("Sync the Django ORM with the configured database")
    __longhelp__ = __shorthelp__ + "\n\nbcfg2-admin syncdb"
    __usage__ = "bcfg2-admin syncdb"
    options = {'configfile': Bcfg2.Options.WEB_CFILE}

    def __call__(self, args):
        # Parse options
        self.opts = Bcfg2.Options.OptionParser(self.options)
        self.opts.parse(args)

        setup_environ(Bcfg2.settings)
        Bcfg2.Server.models.load_models(cfile=self.opts['configfile'])

        try:
            call_command("syncdb", interactive=False, verbosity=0)
            self._database_available = True
        except ImproperlyConfigured:
            self.logger.error("Django configuration problem: %s" %
                format_exc().splitlines()[-1])
            raise SystemExit(-1)
        except:
            self.logger.error("Database update failed: %s" %
                format_exc().splitlines()[-1])
            raise SystemExit(-1)
