""" Handle .cat files, which append lines to and remove lines from
plaintext files """

from Bcfg2.Server.Plugins.Cfg import CfgFilter


class CfgCatFilter(CfgFilter):
    """ CfgCatFilter appends lines to and remove lines from plaintext
    :ref:`server-plugins-generators-Cfg` files"""

    #: Handle .cat files
    __extensions__ = ['cat']

    #: .cat files are deprecated
    deprecated = True

    def modify_data(self, entry, metadata, data):
        datalines = data.strip().split('\n')
        for line in self.data.split('\n'):
            if not line:
                continue
            if line.startswith('+'):
                datalines.append(line[1:])
            elif line.startswith('-'):
                if line[1:] in datalines:
                    datalines.remove(line[1:])
        return "\n".join(datalines) + "\n"
    modify_data.__doc__ = CfgFilter.modify_data.__doc__
