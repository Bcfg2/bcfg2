import django

if django.VERSION[0] > 0:
    from models_new import *
else:
    from models_old import *
