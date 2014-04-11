import os
import Bcfg2.Options
import Bcfg2.DBSettings

config_parsed = False

import django.core.handlers.wsgi


def application(environ, start_response):
    global config_parsed

    # with wsgi, the environment isn't present in os.environ, but
    # is passwd to the application function
    if 'BCFG2_CONFIG_FILE' in environ:
        os.environ['BCFG2_CONFIG_FILE'] = environ['BCFG2_CONFIG_FILE']
    if not config_parsed:
        Bcfg2.Options.get_parser().parse()
        config_parsed = True

    return django.core.handlers.wsgi.WSGIHandler()(environ, start_response)
