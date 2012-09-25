""" An implementation of a simple memory-backed cache. Right now this
doesn't provide many features, but more (time-based expiration, etc.)
can be added as necessary. """


class Cache(dict):
    """ an implementation of a simple memory-backed cache """

    def expire(self, key=None):
        """ expire all items, or a specific item, from the cache """
        if key is None:
            self.clear()
        elif key in self:
            del self[key]
