import os
import Bcfg2.Options
import Bcfg2.DBSettings

Bcfg2.Options.get_parser().parse()

import django.core.handlers.wsgi

def application(environ, start_response):
  return django.core.handlers.wsgi.WSGIHandler()(environ, start_response)
