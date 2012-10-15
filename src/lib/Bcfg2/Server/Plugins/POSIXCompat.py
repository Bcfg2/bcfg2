"""This plugin provides a compatibility layer which turns new-style
POSIX entries into old-style entries.
"""

import Bcfg2.Server.Plugin


class POSIXCompat(Bcfg2.Server.Plugin.Plugin,
                  Bcfg2.Server.Plugin.GoalValidator):
    """POSIXCompat is a goal validator plugin for POSIX entries."""

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.GoalValidator.__init__(self)

    def validate_goals(self, metadata, goals):
        """Verify that we are generating correct old POSIX entries."""
        for goal in goals:
            for entry in goal.getchildren():
                if entry.tag == 'Path' and 'mode' in entry.keys():
                    entry.set('perms', entry.get('mode'))
