""" module for tracking execution time statistics from the bcfg2
server core """


class Statistic(object):
    """ a single named statistic, tracking minimum, maximum, and
    average execution time, and number of invocations """
    def __init__(self, name, initial_value):
        self.name = name
        self.min = float(initial_value)
        self.max = float(initial_value)
        self.ave = float(initial_value)
        self.count = 1

    def add_value(self, value):
        """ add a value to the statistic """
        self.min = min(self.min, value)
        self.max = max(self.max, value)
        self.ave = (((self.ave * (self.count - 1)) + value) / self.count)
        self.count += 1

    def get_value(self):
        """ get a tuple of all the stats tracked on this named item """
        return (self.name, (self.min, self.max, self.ave, self.count))


class Statistics(object):
    """ A collection of named statistics """
    def __init__(self):
        self.data = dict()

    def add_value(self, name, value):
        """ add a value to the named statistic """
        if name not in self.data:
            self.data[name] = Statistic(name, value)
        else:
            self.data[name].add_value(value)

    def display(self):
        """ return a dict of all statistics """
        return dict([value.get_value() for value in list(self.data.values())])
