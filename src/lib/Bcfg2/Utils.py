""" Miscellaneous useful utility functions, classes, etc., that are
used by both client and server.  Stuff that doesn't fit anywhere
else. """

import fcntl
from Bcfg2.Compat import any  # pylint: disable=W0622


class PackedDigitRange(object):
    """ Representation of a set of integer ranges. A range is
    described by a comma-delimited string of integers and ranges,
    e.g.::

        1,10-12,15-20

    Ranges are inclusive on both bounds, and may include 0.  Negative
    numbers are not supported."""

    def __init__(self, *ranges):
        """ May be instantiated in one of two ways::

            PackedDigitRange(<comma-delimited list of ranges>)

        Or::

            PackedDigitRange(<int_or_range>[, <int_or_range>[, ...]])

        E.g., both of the following are valid::

            PackedDigitRange("1-5,7, 10-12")
            PackedDigitRange("1-5", 7, "10-12")
        """
        self.ranges = []
        self.ints = []
        self.str = ",".join(str(r) for r in ranges)
        if len(ranges) == 1 and "," in ranges[0]:
            ranges = ranges[0].split(",")
        for item in ranges:
            item = str(item).strip()
            if item.endswith("-"):
                self.ranges.append((int(item[:-1]), None))
            elif '-' in str(item):
                self.ranges.append(tuple(int(x) for x in item.split('-')))
            else:
                self.ints.append(int(item))

    def includes(self, other):
        """ Return True if ``other`` is included in this range.
        Functionally equivalent to ``other in range``, which should be
        used instead. """
        return other in self

    def __contains__(self, other):
        other = int(other)
        if other in self.ints:
            return True
        return any((end is None and other >= start) or
                   (end is not None and other >= start and other <= end)
                   for start, end in self.ranges)

    def __repr__(self):
        return "%s:%s" % (self.__class__.__name__, str(self))

    def __str__(self):
        return "[%s]" % self.str

    def __len__(self):
        return sum(r[1] - r[0] + 1 for r in self.ranges) + len(self.ints)


def locked(fd):
    """ Acquire a lock on a file """
    try:
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        return True
    return False
