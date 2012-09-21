#!/usr/bin/env python
from django.core.management import execute_manager
try:
    import Bcfg2.settings
except ImportError:
    import sys
    sys.stderr.write("Error: Can't find the Bcfg2.settings module. It appears you've customized things.\nYou'll have to run django-admin.py, passing it your settings module.\n(If the file settings.py does indeed exist, it's causing an ImportError somehow.)\n" % __file__)
    sys.exit(1)

if __name__ == "__main__":
    execute_manager(Bcfg2.settings)
