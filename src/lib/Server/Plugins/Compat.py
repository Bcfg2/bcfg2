'''
   This plugin provides a compatibility layer which turns new-style
   POSIX entries into old-style entries.
'''
__revision__ = '$Revision$'

import Bcfg2.Server.Plugin

# FIXME: We will need this mapping if we decide to change the
#        specification to use lowercase types for new POSIX entry types
#COMPAT_DICT = {'configfile': 'ConfigFile',
#               'device': 'Device',
#               'directory': 'Directory',
#               'permissions': 'Permissions',
#               'symlink': 'SymLink'}

class Compat(Bcfg2.Server.Plugin.Plugin,
             Bcfg2.Server.Plugin.GoalValidator):
    name = 'Compat'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.GoalValidator.__init__(self)

    def validate_goals(self, metadata, goals):
        for goal in goals:
            for entry in goal.getchildren():
                if entry.tag == 'Path':
                    oldentry = entry
                    entry.tag = entry.get('type')
                    # FIXME: use another attribute? old clients only
                    #        know about type=None
                    #entry.set('type', 'Compat')
                    goal.replace(oldentry, entry)
