__revision__ = '$Revision$'

__all__ = [
        'Backup',
        'Bundle',
        'Client',
        'Compare',
        'Group',
        'Init',
        'Minestruct',
        'Perf',
        'Pull',
        'Query',
        'Reports',
        'Snapshots',
        'Tidy',
        'Viz',
        'Xcmd'
        ]

import logging
import lxml.etree
import sys

import Bcfg2.Server.Core
from Bcfg2 import Options


class ModeOperationError(Exception):
    pass


class Mode(object):
    """Help message has not yet been added for mode."""
    __shorthelp__ = 'Shorthelp not defined yet'
    __longhelp__ = 'Longhelp not defined yet'
    __usage__ = None
    __args__ = []

    def __init__(self):
        """Use this to add any arguments needed for the specified mode"""
        self.log = logging.getLogger('Bcfg2.Server.Admin.Mode')
        Options.add_options(Options.SERVER_REPOSITORY)

    def __call__(self, args):
        """
        This will be called to execute the specified mode.

        args are the arguments parsed by metargs
        """
        self.args = args
        pass

    def get_repo_path(self):
        return self.args.repository_path

    def errExit(self, emsg):
        print(emsg)
        raise SystemExit(1)

    def load_stats(self, client):
        stats = lxml.etree.parse("%s/etc/statistics.xml" % self.args.repository_path)
        hostent = stats.xpath('//Node[@name="%s"]' % client)
        if not hostent:
            self.errExit("Could not find stats for client %s" % (client))
        return hostent[0]

    def print_table(self, rows, justify='left', hdr=True, vdelim=" ", padding=1):
        """Pretty print a table

        rows - list of rows ([[row 1], [row 2], ..., [row n]])
        hdr - if True the first row is treated as a table header
        vdelim - vertical delimiter between columns
        padding - # of spaces around the longest element in the column
        justify - may be left,center,right

        """
        hdelim = "="
        justify = {'left': str.ljust,
                   'center': str.center,
                   'right': str.rjust}[justify.lower()]

        """
        Calculate column widths (longest item in each column
        plus padding on both sides)

        """
        cols = list(zip(*rows))
        colWidths = [max([len(str(item)) + 2 * padding for \
                          item in col]) for col in cols]
        borderline = vdelim.join([w * hdelim for w in colWidths])

        # Print out the table
        print(borderline)
        for row in rows:
            print(vdelim.join([justify(str(item), width) for \
                               (item, width) in zip(row, colWidths)]))
            if hdr:
                print(borderline)
                hdr = False


class MetadataCore(Mode):
    """Base class for admin-modes that handle metadata."""
    __plugin_whitelist__ = None
    __plugin_blacklist__ = None
    
    def __init__(self):
        Mode.__init__(self)

        Options.add_options(
            Options.SERVER_PLUGINS,
        )
        Bcfg2.Server.Core.Core.register_options()
        args = Options.bootstrap()
        if self.__plugin_whitelist__ is not None:
            args.server_plugins = [x for x in args.server_plugins
                            if x in self.__plugin_whitelist__]
        elif self.__plugin_blacklist__ is not None:
            args.server_plugins = [x for x in args.server_plugins
                            if x not in self.__plugin_blacklist__]

    def __call__(self, args):
        Mode.__call__(self, args)
        try:
            self.bcore = Bcfg2.Server.Core.Core.from_config(args)
        except Bcfg2.Server.Core.CoreInitError:
            msg = sys.exc_info()[1]
            self.errExit("Core load failed: %s" % msg)
        self.bcore.fam.handle_events_in_interval(5)
        if args.debug:
            self.bcore.fam.debug = True
        self.metadata = self.bcore.metadata


class StructureMode(MetadataCore):
    pass
