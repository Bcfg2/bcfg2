"""
Public transport routines
"""

import traceback

from Bcfg2.Reporting.Transport.base import TransportError, \
    TransportImportError

def load_transport(transport_name, setup):
    """
    Try to load the transport.  Raise TransportImportError on failure
    """
    try:
        mod_name = "%s.%s" % (__name__, transport_name)
        mod = getattr(__import__(mod_name).Reporting.Transport, transport_name)
    except ImportError:
        try:
            mod = __import__(transport_name)
        except:
            raise TransportImportError("Unavailable")
    try:
        cls = getattr(mod, transport_name)
        return cls(setup)
    except:
        raise TransportImportError("Transport unavailable: %s" %
            traceback.format_exc().splitlines()[-1])

def load_transport_from_config(setup):
    """Load the transport in the config... eventually"""
    try:
        return load_transport(setup['reporting_transport'], setup)
    except KeyError:
        raise TransportImportError('Transport missing in config')

