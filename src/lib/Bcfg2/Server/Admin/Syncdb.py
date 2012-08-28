import Bcfg2.settings
import Bcfg2.Options
import Bcfg2.Server.Admin
from Bcfg2.Server.SchemaUpdater import update_database, UpdaterError
from django.core.management import setup_environ

class Syncdb(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = ("Sync the Django ORM with the configured database")
    __longhelp__ = __shorthelp__ + "\n\nbcfg2-admin syncdb"
    __usage__ = "bcfg2-admin syncdb"
    options = {'configfile': Bcfg2.Options.WEB_CFILE}

    def __call__(self, args):
        import Bcfg2.Server.Admin
        Bcfg2.Server.Admin.Mode.__call__(self, args)

        # Parse options
        self.opts = Bcfg2.Options.OptionParser(self.options)
        self.opts.parse(args)

        setup_environ(Bcfg2.settings)
        import Bcfg2.Server.models
        Bcfg2.Server.models.load_models(cfile=self.opts['configfile'])

        try:
            update_database()
        except UpdaterError:
            print("Update failed")
            raise SystemExit(-1)
