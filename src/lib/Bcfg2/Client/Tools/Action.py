"""Action driver"""

import os
import sys
import select
import Bcfg2.Client.Tools
from Bcfg2.Client.Frame import matches_white_list, passes_black_list
from Bcfg2.Compat import input  # pylint: disable=W0622


class Action(Bcfg2.Client.Tools.Tool):
    """Implement Actions"""
    name = 'Action'
    __handles__ = [('PostInstall', None), ('Action', None)]
    __req__ = {'PostInstall': ['name'],
               'Action': ['name', 'timing', 'when', 'command', 'status']}

    def _action_allowed(self, action):
        """ Return true if the given action is allowed to be run by
        the whitelist or blacklist """
        if self.setup['decision'] == 'whitelist' and \
           not matches_white_list(action, self.setup['decision_list']):
            self.logger.info("In whitelist mode: suppressing Action: %s" %
                             action.get('name'))
            return False
        if self.setup['decision'] == 'blacklist' and \
           not passes_black_list(action, self.setup['decision_list']):
            self.logger.info("In blacklist mode: suppressing Action: %s" %
                             action.get('name'))
            return False
        return True

    def RunAction(self, entry):
        """This method handles command execution and status return."""
        shell = False
        shell_string = ''
        if entry.get('shell', 'false') == 'true':
            shell = True
            shell_string = '(in shell) '

        if not self.setup['dryrun']:
            if self.setup['interactive']:
                prompt = ('Run Action %s%s, %s: (y/N): ' %
                          (shell_string, entry.get('name'),
                           entry.get('command')))
                # flush input buffer
                while len(select.select([sys.stdin.fileno()], [], [],
                                        0.0)[0]) > 0:
                    os.read(sys.stdin.fileno(), 4096)
                ans = input(prompt)
                if ans not in ['y', 'Y']:
                    return False
            if self.setup['servicemode'] == 'build':
                if entry.get('build', 'true') == 'false':
                    self.logger.debug("Action: Deferring execution of %s due "
                                      "to build mode" % entry.get('command'))
                    return False
            self.logger.debug("Running Action %s %s" %
                              (shell_string, entry.get('name')))
            rv = self.cmd.run(entry.get('command'), shell=shell)
            self.logger.debug("Action: %s got return code %s" %
                              (entry.get('command'), rv.retval))
            entry.set('rc', str(rv.retval))
            return entry.get('status', 'check') == 'ignore' or rv.success
        else:
            self.logger.debug("In dryrun mode: not running action: %s" %
                              (entry.get('name')))
            return False

    def VerifyAction(self, dummy, _):
        """Actions always verify true."""
        return True

    def VerifyPostInstall(self, dummy, _):
        """Actions always verify true."""
        return True

    def InstallAction(self, entry):
        """Run actions as pre-checks for bundle installation."""
        if entry.get('timing') != 'post':
            return self.RunAction(entry)
        return True

    def InstallPostInstall(self, entry):
        """ Install a deprecated PostInstall entry """
        self.logger.warning("Installing deprecated PostInstall entry %s" %
                            entry.get("name"))
        return self.InstallAction(entry)

    def BundleUpdated(self, bundle, states):
        """Run postinstalls when bundles have been updated."""
        for postinst in bundle.findall("PostInstall"):
            if not self._action_allowed(postinst):
                continue
            self.cmd.run(postinst.get('name'))
        for action in bundle.findall("Action"):
            if action.get('timing') in ['post', 'both']:
                if not self._action_allowed(action):
                    continue
                states[action] = self.RunAction(action)

    def BundleNotUpdated(self, bundle, states):
        """Run Actions when bundles have not been updated."""
        for action in bundle.findall("Action"):
            if action.get('timing') in ['post', 'both'] and \
               action.get('when') != 'modified':
                if not self._action_allowed(action):
                    continue
                states[action] = self.RunAction(action)
