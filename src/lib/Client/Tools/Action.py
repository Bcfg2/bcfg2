'''Action driver'''
__revision__ = '$Revision$'

import Bcfg2.Client.Tools

# <Action timing='pre|post|both' name='name' command='cmd text' when='always|modified'
#         status='ignore|check'/>
# <PostInstall name='foo'/>
#   => <Action timing='post' when='modified' name='n' command='foo' status='ignore'/>

class Action(Bcfg2.Client.Tools.Tool):
    '''Implement Actions'''
    name = 'Action'
    __handles__ = [('PostInstall', None), ('Action', None)]
    __req__ = {'PostInstall': ['name'],
               'Action':['name', 'timing', 'when', 'command', 'status']}

    def RunAction(self, entry):
        '''This method handles command execution and status return'''
        if not self.setup['dryrun']:
            if self.setup['interactive']:
                prompt = 'Run Action %s, %s: (y/N): ' % (entry.get('name'), entry.get('command'))
                if raw_input(prompt) not in ['y', 'Y']:
                    return False
            self.logger.debug("Running Action %s" % (entry.get('name')))
            rc = self.cmd.run(entry.get('command'))[0]
            self.logger.debug("Action: %s got rc %s" % (entry.get('command'), rc))
            entry.set('rc', str(rc))
            if entry.get('status', 'check') == 'ignore':
                return True
            else:
                return rc == 0
        else:
            return False

    def VerifyAction(self, dummy, _):
        '''Actions always verify true'''
        return True

    def VerifyPostInstall(self, dummy, _):
        '''Actions always verify true'''
        return True

    def InstallAction(self, entry):
        '''Run actions as pre-checks for bundle installation'''
        if entry.get('timing') != 'post':
            return self.RunAction(entry)
        return True

    def InstallPostInstall(self, entry):
        return self.InstallAction(self, entry)

    def BundleUpdated(self, bundle, states):
        '''Run postinstalls when bundles have been updated'''
        for postinst in bundle.findall("PostInstall"):
            self.cmd.run(postinst.get('name'))
        for action in bundle.findall("Action"):
            if action.get('timing') in ['post', 'both']:
                states[action] = self.RunAction(action)

    def BundleNotUpdated(self, bundle, states):
        '''Run Actions when bundles have not been updated'''
        for action in bundle.findall("Action"):
            if action.get('timing') in ['post', 'both'] and \
               action.get('when') != 'modified':
                states[action] = self.RunAction(action)
