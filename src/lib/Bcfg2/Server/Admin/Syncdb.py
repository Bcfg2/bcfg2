import Bcfg2.settings
import Bcfg2.Options
import Bcfg2.Server.Admin
from django.core.management import setup_environ

class Syncdb(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = ("Sync the Django ORM with the configured database")
    __longhelp__ = __shorthelp__ + "\n\nbcfg2-admin syncdb"
    __usage__ = "bcfg2-admin syncdb"
    options = {'configfile': Bcfg2.Options.CFILE,
               'repo': Bcfg2.Options.SERVER_REPOSITORY}

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)

        # Parse options
        self.opts = Bcfg2.Options.OptionParser(self.options)
        self.opts.parse(args)

        # we have to set up the django environment before we import
        # the syncdb command, but we have to wait to set up the
        # environment until we've read the config, which has to wait
        # until we've parsed options.  it's a windy, twisting road.
        Bcfg2.settings.read_config(cfile=self.opts['configfile'],
                                   repo=self.opts['repo'])
        setup_environ(Bcfg2.settings)
        import Bcfg2.Server.models
        Bcfg2.Server.models.load_models(cfile=self.opts['configfile'])

        from django.core.management.commands import syncdb

        cmd = syncdb.Command()
        cmd.handle_noargs(interactive=False)
