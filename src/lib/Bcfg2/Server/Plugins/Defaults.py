"""This generator provides rule-based entry mappings."""

import Bcfg2.Server.Plugin
import Bcfg2.Server.Plugins.Rules


class Defaults(Bcfg2.Server.Plugins.Rules.Rules,
               Bcfg2.Server.Plugin.GoalValidator):
    """Set default attributes on bound entries"""
    __author__ = 'bcfg-dev@mcs.anl.gov'

    # Rules is a Generator that happens to implement all of the
    # functionality we want, so we overload it, but Defaults should
    # _not_ handle any entries; it does its stuff in the structure
    # validation phase.  so we overload Handle(s)Entry and HandleEvent
    # to ensure that Defaults handles no entries, even though it's a
    # Generator.

    def HandlesEntry(self, entry, metadata):
        return False

    def HandleEvent(self, event):
        Bcfg2.Server.Plugin.XMLDirectoryBacked.HandleEvent(self, event)

    def validate_goals(self, metadata, config):
        """ Apply defaults """
        for struct in config.getchildren():
            for entry in struct.getchildren():
                try:
                    self.BindEntry(entry, metadata)
                except Bcfg2.Server.Plugin.PluginExecutionError:
                    # either no matching defaults (which is okay),
                    # or multiple matching defaults (which is not
                    # okay, but is logged).  either way, we don't
                    # care about the error.
                    pass

    @property
    def _regex_enabled(self):
        """ Defaults depends on regex matching, so force it enabled """
        return True
