""" Compatibility imports for Django. """

from django import VERSION
from django.db import transaction

# Django 1.6 deprecated commit_on_success() and introduced atomic() with
# similar semantics.
if VERSION[0] == 1 and VERSION[1] < 6:
    transaction.atomic = transaction.commit_on_success

try:
    # Django < 1.6
    from django.conf.urls.defaults import url, patterns
except ImportError:
    # Django > 1.6
    from django.conf.urls import url, patterns
