"""
  Support for metadata.Hierarchy, which adds
  group hierarchy information with the profile
  as anchor.
"""

import copy

import Bcfg2.Server.Plugin
from Bcfg2.Server.Cache import Cache


class Hierarchy(Bcfg2.Server.Plugin.Plugin,
                Bcfg2.Server.Plugin.Connector):
    """ adds the group hierarchy information to metadata
    this information is lost in metadata.groups """

    def __init__(self, core):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self._cache = Bcfg2.Server.Cache.Cache("Hierarchy")

        # inform us when a cache has been expired
        # if a metadata object changed we have to
        #  expire the cache as well
        Bcfg2.Server.Cache.add_expire_hook(self._cache_expire_handler)

    __init__.__doc__ = Bcfg2.Server.Plugin.Plugin.__init__.__doc__

    def get_additional_data(self, metadata):
        """ Parse through all groups of this client
         add hierarchy information so it can be used
         by other tools later """
        self.debug_log("Hierarchy: Getting hierarchy for %s" %
                       metadata.hostname)
        if metadata.hostname in self._cache:
            return self._cache[metadata.hostname]

        # profile is our anchor group
        # if we don't add it here we get a circular reference
        visited_groups = set([metadata.profile])
        hierarchy = dict()
        for grp in metadata.groups:
            hierarchy[grp] = set()
            # get all children of the group
            for child in self.core.metadata.groups_xml.xdata.xpath(
                    "//Groups/Group[@name='%s']//Group" % grp):
                # safeguard so only groups are added that this
                # client is part of
                if child.get('name') in metadata.groups:
                    hierarchy[grp].add(child.get('name'))
                    visited_groups.add(child.get('name'))

        # postprocessing for groups that are added by probes or other plugins
        # these are children of profile in the hierarchy
        for grp in (set(metadata.groups) - visited_groups):
            hierarchy[metadata.profile].add(grp)

        self._cache[metadata.hostname] = hierarchy
        return hierarchy

    def _cache_expire_handler(self, tags, exact, count):
        """ listens for caches that were expired.
        If the metadata cache was expired for
        a single host or entirely, then the local
        cache is cleared as well. """
        self.logger.debug("Hierarchy: Got Cache expire event. "
                          "Tags: %s, exact=%s, count=%s" %
                          (tags, exact, count))
        if not tags or "Hierarchy" in tags:
            return
        try:
            # tags are tuples (hostname, "Metadata") to expire
            # a single hostname
            # or ("Metadata",) if the whole metadata cache was cleared
            if len(tags) == 2 and "Metadata" in tags:
                if tags[0] == "Metadata":
                    self._cache.expire()
                    self.debug_log("Hierarchy: Expiring cache %s %s" %
                                   (str(tags), str(exact)))
                else:
                    self._cache.expire(tags[0])
                    self.debug_log("Hierarchy: Expiring cache %s %s" %
                                   (str(tags), str(exact)))
        except Exception as e:
            self.logger.warn("Hierarchy: Error choosing if"
                             " cache should be expired. Expiring anyway. "
                             "Tags %s, "
                             "Error: %s"
                             % (str(tags), e))
            self._cache.expire()

    def set_debug(self, debug):
        rv = Bcfg2.Server.Plugin.Plugin.set_debug(self, debug)
        return rv

    set_debug.__doc__ = Bcfg2.Server.Plugin.Plugin.set_debug.__doc__
