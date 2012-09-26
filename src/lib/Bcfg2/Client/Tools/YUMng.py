""" YUM driver called 'YUMng' for backwards compat """

from Bcfg2.Client.Tools.YUM import YUM


class YUMng(YUM):
    """ YUM driver called 'YUMng' for backwards compat """
    deprecated = True
    conflicts = ['YUM24', 'RPM', 'RPMng']
