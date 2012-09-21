import os
import Bcfg2.settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'Bcfg2.settings'
import django.core.handlers.wsgi

def application(environ, start_response):
  if 'BCFG2_CONFIG_FILE' in environ:
       Bcfg2.settings.read_config(cfile=environ['BCFG2_CONFIG_FILE'])
  return django.core.handlers.wsgi.WSGIHandler()(environ, start_response)
