"""This plugin provides a compatibility layer which turns new-style
POSIX entries into old-style entries.
"""

__revision__ = '$Revision$'

import Bcfg2.Server.Plugin

COMPAT_DICT = {'file': 'ConfigFile',
               'directory': 'Directory',
               'permissions': 'Permissions',
               'symlink': 'SymLink'}


class POSIXCompat(Bcfg2.Server.Plugin.Plugin,
                  Bcfg2.Server.Plugin.GoalValidator):
    """POSIXCompat is a goal validator plugin for POSIX entries"""
    name = 'POSIXCompat'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.GoalValidator.__init__(self)

    def validate_goals(self, metadata, goals):
        """Verify that we are generating correct old
        Cfg/Directory/Symlink entries"""
        for goal in goals:
            for entry in goal.getchildren():
                if entry.tag == 'Path' and \
                   entry.get('type') not in ['nonexistent', 'device']:
                    # Use new entry 'type' attribute to map old entry tags
                    oldentry = entry
                    entry.tag = COMPAT_DICT[entry.get('type')]
                    del entry.attrib['type']
                    goal.replace(oldentry, entry)
