""" Use old-style service modes for older clients """

import Bcfg2.Server.Plugin


class ServiceCompat(Bcfg2.Server.Plugin.Plugin,
                    Bcfg2.Server.Plugin.GoalValidator):
    """ Use old-style service modes for older clients """

    create = False

    __author__ = 'bcfg-dev@mcs.anl.gov'
    mode_map = {('true', 'true'): 'default',
                ('interactive', 'true'): 'interactive_only',
                ('false', 'false'): 'manual'}

    def validate_goals(self, metadata, config):
        """ Apply defaults """
        if metadata.version_info and metadata.version_info >= (1, 3, 0, '', 0):
            # do not care about a client that is _any_ 1.3.0 release
            # (including prereleases and RCs)
            return

        for entry in config.xpath("//BoundService|//Service"):
            mode_key = (entry.get("restart", "true").lower(),
                        entry.get("install", "true").lower())
            try:
                mode = self.mode_map[mode_key]
            except KeyError:
                self.logger.info("Could not map restart and install settings "
                                 "of %s:%s to an old-style Service mode for "
                                 "%s; using 'manual'" %
                                 (entry.tag, entry.get("name"),
                                  metadata.hostname))
                mode = "manual"
            entry.set("mode", mode)
