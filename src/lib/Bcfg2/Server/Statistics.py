""" Module for tracking execution time statistics from the Bcfg2
server core.  This data is exposed by
:func:`Bcfg2.Server.Core.BaseCore.get_statistics`."""

import time
from Bcfg2.Compat import wraps


class Statistic(object):
    """ A single named statistic, tracking minimum, maximum, and
    average execution time, and number of invocations. """

    def __init__(self, name, initial_value):
        """
        :param name: The name of this statistic
        :type name: string
        :param initial_value: The initial value to be added to this
                              statistic
        :type initial_value: int or float
        """
        self.name = name
        self.min = float(initial_value)
        self.max = float(initial_value)
        self.ave = float(initial_value)
        self.count = 1

    def add_value(self, value):
        """ Add a value to the statistic, recalculating the various
        metrics.

        :param value: The value to add to this statistic
        :type value: int or float
        """
        self.min = min(self.min, float(value))
        self.max = max(self.max, float(value))
        self.count += 1
        self.ave = (((self.ave * (self.count - 1)) + value) / self.count)

    def get_value(self):
        """ Get a tuple of all the stats tracked on this named item.
        The tuple is in the format::

            (<name>, (min, max, average, number of values))

        This makes it very easy to cast to a dict in
        :func:`Statistics.display`.

        :returns: tuple
        """
        return (self.name, (self.min, self.max, self.ave, self.count))

    def __repr__(self):
        return "%s(%s, (min=%s, avg=%s, max=%s, count=%s))" % (
            self.__class__.__name__,
            self.name, self.min, self.ave, self.max, self.count)


class Statistics(object):
    """ A collection of named :class:`Statistic` objects. """

    def __init__(self):
        self.data = dict()

    def add_value(self, name, value):
        """ Add a value to the named :class:`Statistic`.  This just
        proxies to :func:`Statistic.add_value` or the
        :class:`Statistic` constructor as appropriate.

        :param name: The name of the :class:`Statistic` to add the
                     value to
        :type name: string
        :param value: The value to add to the Statistic
        :type value: int or float
        """
        if name not in self.data:
            self.data[name] = Statistic(name, value)
        else:
            self.data[name].add_value(value)

    def display(self):
        """ Return a dict of all :class:`Statistic` object values.
        Keys are the statistic names, and values are tuples of the
        statistic metrics as returned by
        :func:`Statistic.get_value`. """
        return dict([value.get_value() for value in list(self.data.values())])


#: A module-level :class:`Statistics` objects used to track all
#: execution time metrics for the server.
stats = Statistics()  # pylint: disable=invalid-name


class track_statistics(object):  # pylint: disable=invalid-name
    """ Decorator that tracks execution time for the given method with
    :mod:`Bcfg2.Server.Statistics` for reporting via ``bcfg2-admin
    perf`` """

    def __init__(self, name=None):
        """
        :param name: The name under which statistics for this function
                     will be tracked.  By default, the name will be
                     the name of the function concatenated with the
                     name of the class the function is a member of.
        :type name: string
        """
        # if this is None, it will be set later during __call_
        self.name = name

    def __call__(self, func):
        if self.name is None:
            self.name = func.__name__

        @wraps(func)
        def inner(obj, *args, **kwargs):
            """ The decorated function """
            name = "%s:%s" % (obj.__class__.__name__, self.name)

            start = time.time()
            try:
                return func(obj, *args, **kwargs)
            finally:
                stats.add_value(name, time.time() - start)

        return inner
