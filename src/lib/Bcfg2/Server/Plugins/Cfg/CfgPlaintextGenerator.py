""" CfgPlaintextGenerator is a
:class:`Bcfg2.Server.Plugins.Cfg.CfgGenerator` that handles plain text
(i.e., non-templated) :ref:`server-plugins-generators-cfg` files."""

from Bcfg2.Server.Plugins.Cfg import CfgGenerator


class CfgPlaintextGenerator(CfgGenerator):
    """ CfgPlaintextGenerator is a
    :class:`Bcfg2.Server.Plugins.Cfg.CfgGenerator` that handles plain
    text (i.e., non-templated) :ref:`server-plugins-generators-cfg`
    files. The base Generator class already implements this
    functionality, so CfgPlaintextGenerator doesn't need to do
    anything itself."""

    #: Very low priority to avoid matching host- or group-specific
    #: files with other extensions -- e.g., .genshi, .crypt, etc.
    __priority__ = 100
