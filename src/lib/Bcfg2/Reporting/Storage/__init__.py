"""
Public storage routines
"""

import traceback

from Bcfg2.Reporting.Storage.base import StorageError, \
    StorageImportError

def load_storage(storage_name, setup):
    """
    Try to load the storage.  Raise StorageImportError on failure
    """
    try:
        mod_name = "%s.%s" % (__name__, storage_name)
        mod = getattr(__import__(mod_name).Reporting.Storage, storage_name)
    except ImportError:
        try:
            mod = __import__(storage_name)
        except:
            raise StorageImportError("Unavailable")
    try:
        cls = getattr(mod, storage_name)
        return cls(setup)
    except:
        raise StorageImportError("Storage unavailable: %s" %
            traceback.format_exc().splitlines()[-1])

def load_storage_from_config(setup):
    """Load the storage in the config... eventually"""
    return load_storage('DjangoORM', setup)

