'''Helper functions for reports'''

class BatchFetch(object):
    '''Fetch Django objects in smaller batches to save memory'''

    def __init__(self, obj, step=10000):
        self.count = 0
        self.block_count = 0
        self.obj = obj
        self.data = None
        self.step = step
        self.max = obj.count()

    def __iter__(self):
        return self

    def next(self):
        '''Return the next object from our array and fetch from the
           database when needed'''
        if self.block_count + self.count - self.step == self.max:
            raise StopIteration
        if self.block_count == 0 or self.count == self.step:
            # Without list() this turns into LIMIT 1 OFFSET x queries
            self.data = list(self.obj.all()[self.block_count: \
                                   (self.block_count + self.step)])
            self.block_count += self.step
            self.count = 0
        self.count += 1
        return self.data[self.count - 1]

