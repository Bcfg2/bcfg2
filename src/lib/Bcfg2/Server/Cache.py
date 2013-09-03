""" ``Bcfg2.Server.Cache`` is an implementation of a simple
memory-backed cache. Right now this doesn't provide many features, but
more (time-based expiration, etc.)  can be added as necessary.

The normal workflow is to get a Cache object, which is simply a dict
interface to the unified cache that automatically uses a certain tag
set.  For instance:

.. code-block:: python

    groupcache = Bcfg2.Server.Cache.Cache("Probes", "probegroups")
    groupcache['foo.example.com'] = ['group1', 'group2']

This would create a Cache object that automatically tags its entries
with ``frozenset(["Probes", "probegroups"])``, and store the list
``['group1', 'group1']`` with the *additional* tag
``foo.example.com``.  So the unified backend cache would then contain
a single entry:

.. code-block:: python

    {frozenset(["Probes", "probegroups", "foo.example.com"]):
     ['group1', 'group2']}

In addition to the dict interface, Cache objects (returned from
:func:`Bcfg2.Server.Cache.Cache`) have one additional method,
``expire()``, which is mostly identical to
:func:`Bcfg2.Server.Cache.expire`, except that it is specific to the
tag set of the cache object.  E.g., to expire all ``foo.example.com``
records for a given cache, you could do:

.. code-block:: python

    groupcache = Bcfg2.Server.Cache.Cache("Probes", "probegroups")
    groupcache.expire("foo.example.com")

This is mostly functionally identical to:

.. code-block:: python

    Bcfg2.Server.Cache.expire("Probes", "probegroups", "foo.example.com")

It's not completely identical, though; the first example will expire,
at most, exactly one item from the cache.  The second example will
expire all items that are tagged with a superset of the given tags.
To illustrate the difference, consider the following two examples:

.. code-block:: python

    groupcache = Bcfg2.Server.Cache.Cache("Probes")
    groupcache.expire("probegroups")

    Bcfg2.Server.Cache.expire("Probes", "probegroups")

The former will not expire any data, because there is no single datum
tagged with ``"Probes", "probegroups"``.  The latter will expire *all*
items tagged with ``"Probes", "probegroups"`` -- i.e., the entire
cache.  In this case, the latter call is equivalent to:

.. code-block:: python

    groupcache = Bcfg2.Server.Cache.Cache("Probes", "probegroups")
    groupcache.expire()

"""

from Bcfg2.Compat import MutableMapping


class _Cache(MutableMapping):
    """ The object returned by :func:`Bcfg2.Server.Cache.Cache` that
    presents a dict-like interface to the portion of the unified cache
    that uses the specified tags. """
    def __init__(self, registry, tags):
        self._registry = registry
        self._tags = tags

    def __getitem__(self, key):
        return self._registry[self._tags | set([key])]

    def __setitem__(self, key, value):
        self._registry[self._tags | set([key])] = value

    def __delitem__(self, key):
        del self._registry[self._tags | set([key])]

    def __iter__(self):
        for item in self._registry.iterate(*self._tags):
            yield list(item.difference(self._tags))[0]

    def keys(self):
        """ List cache keys """
        return list(iter(self))

    def __len__(self):
        return len(list(iter(self)))

    def expire(self, key=None):
        """ expire all items, or a specific item, from the cache """
        if key is None:
            expire(*self._tags)
        else:
            tags = self._tags | set([key])
            # py 2.5 doesn't support mixing *args and explicit keyword
            # args
            kwargs = dict(exact=True)
            expire(*tags, **kwargs)

    def __repr__(self):
        return repr(dict(self))

    def __str__(self):
        return str(dict(self))


class _CacheRegistry(dict):
    """ The grand unified cache backend which contains all cache
    items. """

    def iterate(self, *tags):
        """ Iterate over all items that match the given tags *and*
        have exactly one additional tag.  This is used to get items
        for :class:`Bcfg2.Server.Cache._Cache` objects that have been
        instantiated via :func:`Bcfg2.Server.Cache.Cache`. """
        tags = frozenset(tags)
        for key in self.keys():
            if key.issuperset(tags) and len(key.difference(tags)) == 1:
                yield key

    def iter_all(self, *tags):
        """ Iterate over all items that match the given tags,
        regardless of how many additional tags they have (or don't
        have). This is used to expire all cache data that matches a
        set of tags. """
        tags = frozenset(tags)
        for key in list(self.keys()):
            if key.issuperset(tags):
                yield key


_cache = _CacheRegistry()  # pylint: disable=C0103
_hooks = []  # pylint: disable=C0103


def Cache(*tags):  # pylint: disable=C0103
    """ A dict interface to the cache data tagged with the given
    tags. """
    return _Cache(_cache, frozenset(tags))


def expire(*tags, **kwargs):
    """ Expire all items, a set of items, or one specific item from
    the cache.  If ``exact`` is set to True, then if the given tag set
    doesn't match exactly one item in the cache, nothing will be
    expired. """
    exact = kwargs.pop("exact", False)
    count = 0
    if not tags:
        count = len(_cache)
        _cache.clear()
    elif exact:
        if frozenset(tags) in _cache:
            count = 1
            del _cache[frozenset(tags)]
    else:
        for match in _cache.iter_all(*tags):
            count += 1
            del _cache[match]

    for hook in _hooks:
        hook(tags, exact, count)


def add_expire_hook(func):
    """ Add a hook that will be called when an item is expired from
    the cache.  The callable passed in must take three options: the
    first will be the tag set that was expired; the second will be the
    state of the ``exact`` flag (True or False); and the third will be
    the number of items that were expired from the cache. """
    _hooks.append(func)
