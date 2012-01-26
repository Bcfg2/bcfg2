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
import Bcfg2.Options
# Compatibility import
from Bcfg2.Bcfg2Py3k import ConfigParser


class ModeOperationError(Exception):
    pass


class Mode(object):
    """Help message has not yet been added for mode."""
    __shorthelp__ = 'Shorthelp not defined yet'
    __longhelp__ = 'Longhelp not defined yet'
    __usage__ = None
    __args__ = []

    def __init__(self, setup):
        self.setup = setup
        self.configfile = setup['configfile']
        self.__cfp = False
        self.log = logging.getLogger('Bcfg2.Server.Admin.Mode')
        if self.__usage__ is not None:
            setup.hm = self.__usage__

    def getCFP(self):
        if not self.__cfp:
            self.__cfp = ConfigParser.ConfigParser()
            self.__cfp.read(self.configfile)
        return self.__cfp

    cfp = property(getCFP)

    def __call__(self, args):
        pass

    def errExit(self, emsg):
        print(emsg)
        raise SystemExit(1)

    def load_stats(self, client):
        stats = lxml.etree.parse("%s/etc/statistics.xml" % self.setup['repo'])
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
    
    def __init__(self, setup):
        Mode.__init__(self, setup)
        if self.__plugin_whitelist__ is not None:
            setup['plugins'] = [p for p in setup['plugins']
                                if p in self.__plugin_whitelist__]
        elif self.__plugin_blacklist__ is not None:
            setup['plugins'] = [p for p in setup['plugins']
                                if p not in self.__plugin_blacklist__]

        try:
            self.bcore = \
                Bcfg2.Server.Core.Core(setup['repo'],
                                       setup['plugins'],
                                       setup['password'],
                                       setup['encoding'],
                                       filemonitor=setup['filemonitor'])
            if setup['event debug']:
                self.bcore.fam.debug = True
        except Bcfg2.Server.Core.CoreInitError:
            msg = sys.exc_info()[1]
            self.errExit("Core load failed: %s" % msg)
        self.bcore.fam.handle_events_in_interval(5)
        self.metadata = self.bcore.metadata


class StructureMode(MetadataCore):
    pass
