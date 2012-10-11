""" RPM driver called 'RPMng' for backwards compat """

from Bcfg2.Client.Tools.RPM import RPM


class RPMng(RPM):
    """ RPM driver called 'RPMng' for backwards compat """
    deprecated = True
    name = "RPM"
