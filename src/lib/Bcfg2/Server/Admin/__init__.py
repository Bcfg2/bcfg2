""" Base classes for admin modes """

import re
import sys
import logging
import lxml.etree
import Bcfg2.Server.Core
import Bcfg2.Options
from Bcfg2.Compat import ConfigParser, walk_packages

__all__ = [m[1] for m in walk_packages(path=__path__)]


class Mode(object):
    """ Base object for admin modes.  Docstrings are used as help
    messages, so if you are seeing this, a help message has not yet
    been added for this mode. """
    __usage__ = None
    __args__ = []

    def __init__(self, setup):
        self.setup = setup
        self.configfile = setup['configfile']
        self.__cfp = False
        self.log = logging.getLogger('Bcfg2.Server.Admin.Mode')
        usage = "bcfg2-admin %s" % self.__class__.__name__.lower()
        if self.__usage__ is not None:
            usage += " " + self.__usage__
        setup.hm = usage

    def getCFP(self):
        """ get a config parser for the Bcfg2 config file """
        if not self.__cfp:
            self.__cfp = ConfigParser.ConfigParser()
            self.__cfp.read(self.configfile)
        return self.__cfp

    cfp = property(getCFP)

    def __call__(self, args):
        raise NotImplementedError

    @classmethod
    def usage(cls, rv=1):
        """ Exit with a long usage message """
        print(re.sub(r'\s{2,}', ' ', cls.__doc__.strip()))
        print("")
        print("Usage:")
        usage = "bcfg2-admin %s" % cls.__name__.lower()
        if cls.__usage__ is not None:
            usage += " " + cls.__usage__
        print("  %s" % usage)
        raise SystemExit(rv)

    def shutdown(self):
        """ Perform any necessary shtudown tasks for this mode """
        pass

    def errExit(self, emsg):
        """ exit with an error """
        print(emsg)
        raise SystemExit(1)

    def load_stats(self, client):
        """ Load static statistics from the repository """
        stats = lxml.etree.parse("%s/etc/statistics.xml" % self.setup['repo'])
        hostent = stats.xpath('//Node[@name="%s"]' % client)
        if not hostent:
            self.errExit("Could not find stats for client %s" % (client))
        return hostent[0]

    def print_table(self, rows, justify='left', hdr=True, vdelim=" ",
                    padding=1):
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

        # Calculate column widths (longest item in each column
        # plus padding on both sides)
        cols = list(zip(*rows))
        col_widths = [max([len(str(item)) + 2 * padding
                           for item in col]) for col in cols]
        borderline = vdelim.join([w * hdelim for w in col_widths])

        # Print out the table
        print(borderline)
        for row in rows:
            print(vdelim.join([justify(str(item), width)
                               for (item, width) in zip(row, col_widths)]))
            if hdr:
                print(borderline)
                hdr = False


# pylint wants MetadataCore and StructureMode to be concrete classes
# and implement __call__, but they aren't and they don't, so we
# disable that warning
# pylint: disable=W0223

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

        # admin modes don't need to watch for changes.  one shot is fine here.
        setup['filemonitor'] = 'pseudo'
        try:
            self.bcore = Bcfg2.Server.Core.BaseCore(setup)
        except Bcfg2.Server.Core.CoreInitError:
            msg = sys.exc_info()[1]
            self.errExit("Core load failed: %s" % msg)
        self.bcore.load_plugins()
        self.bcore.fam.handle_event_set()
        self.metadata = self.bcore.metadata

    def shutdown(self):
        if hasattr(self, 'bcore'):
            self.bcore.shutdown()


class StructureMode(MetadataCore):  # pylint: disable=W0223
    """ Base class for admin modes that handle structure plugins """
    pass
