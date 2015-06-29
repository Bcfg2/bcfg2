import os
import Bcfg2.settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'Bcfg2.settings'
import django

if django.VERSION[0] == 1 and django.VERSION[1] >= 7:
    from django.core.wsgi import get_wsgi_application
    def application(environ, start_response):
        if 'BCFG2_CONFIG_FILE' in environ:
            Bcfg2.settings.read_config(cfile=environ['BCFG2_CONFIG_FILE'])
        return get_wsgi_application()(environ, start_response)

else:
    import django.core.handlers.wsgi
    def application(environ, start_response):
        if 'BCFG2_CONFIG_FILE' in environ:
            Bcfg2.settings.read_config(cfile=environ['BCFG2_CONFIG_FILE'])
        return django.core.handlers.wsgi.WSGIHandler()(environ, start_response)
