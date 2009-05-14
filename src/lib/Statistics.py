
class Statistic(object):
    def __init__(self, name, initial_value):
        self.name = name
        self.min = float(initial_value)
        self.max = float(initial_value)
        self.ave = float(initial_value)
        self.count = 1

    def add_value(self, value):
        if value < self.min:
            self.min = value
        if value > self.max:
            self.max = value
        self.count += 1
        self.ave = (((self.ave * (self.count - 1)) + value) / self.count )

    def get_value(self):
        return (self.name, (self.min, self.max, self.ave))

class Statistics(object):
    def __init__(self):
        self.data = dict()

    def add_value(self, name, value):
        if name not in self.data:
            self.data[name] = Statistic(name, value)
        else:
            self.data[name].add_value(value)

    def display(self):
        return dict([value.get_value() for value in self.data.values()])
            
