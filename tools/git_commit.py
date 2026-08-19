#!/usr/bin/env python
""" Trigger script to commit selected changes to a local repository
back to git.  To use this script, enable the Trigger plugin, put this
script in /var/lib/bcfg2/Trigger/, and create /etc/bcfg2-commit.conf.

The config file, /etc/bcfg2-commit.conf, may contain four options:

* "config" in [global] is the path to the Bcfg2 server config file.
  (Default: /etc/bcfg2.conf)
* "commit" in [global] is a comma-separated list of globs giving the
  paths that should be committed back to the repository.  Default is
  'SSLCA/*, SSHbase/*, Cfg/*', which will commit data back for SSLCA,
  SSHbase, Cfg, FileProbes, etc., but not, for instance, Probes/probed.xml.
  You may wish to add Metadata/clients.xml to the commit list.
* "debug" and "verbose" in [logging] let you set the log level for
  git_commit.py itself.
"""

import os
import sys
import git
import logging
import Bcfg2.Options
import Bcfg2.Logger
from fnmatch import fnmatch


def list_changed_files(repo):
    return [d for d in repo.index.diff(None)
            if (d.a_blob is not None and not d.deleted_file and
                not d.renamed and not d.new_file)]


class CLI(object):
    options = [
        Bcfg2.Options.BooleanOption(
            '-n', '--dry-run', help='Do not actually commit something'),
        Bcfg2.Options.PathOption(
            '-c', '--config', action=Bcfg2.Options.ConfigFileAction,
            help='Configuration file', default='/etc/bcfg2-commit.conf'),
        Bcfg2.Options.Common.repository,
        Bcfg2.Options.Common.syslog,

        Bcfg2.Options.PathOption(
            cf=('server', 'vcs_root'), default='<repository>',
            help='VCS repository root'),
        Bcfg2.Options.Option(
            cf=('global', 'commit'), type=Bcfg2.Options.Types.comma_list,
            default=['SSLCA/*', 'SSHbase/*', 'Cfg/*'], help=''),
        Bcfg2.Options.PathOption(
            cf=('global', 'config'), action=Bcfg2.Options.ConfigFileAction,
            default='/etc/bcfg2.conf'),

        # Trigger arguments
        Bcfg2.Options.PositionalArgument('hostname', help='Client hostname'),
        Bcfg2.Options.Option('-p', '--profile', metavar='<profile>',
            help='Client profile'),
        Bcfg2.Options.Option('-g', '--groups', metavar='<group1:...:groupN>',
            help='All client groups'),
    ]

    def __init__(self):
        Bcfg2.Options.get_parser(
            description='Trigger script to commit selected changes to a local '
                        'repository back to git.',
            components=[self, Bcfg2.Logger._OptionContainer]).parse()
        self.progname = os.path.basename(sys.argv[0])
        self.logger = logging.getLogger(self.progname)

    def add_to_commit(self, repo, path, relpath):
        for pattern in Bcfg2.Options.setup.commit:
            if fnmatch(path, os.path.join(relpath, pattern)):
                self.logger.debug('Adding %s to commit' % path)
                repo.index.add([path])
                return True
        return False

    def run(self):
        if Bcfg2.Options.setup.dry_run:
            self.logger.info('In dry-run mode, changes will not be committed')

        if 'vcs_root' in Bcfg2.Options.setup:
            gitroot = Bcfg2.Options.setup.vcs_root

            if not Bcfg2.Options.setup.repository.startswith(gitroot):
                logger.error('Bcfg2 repo %s is not inside Git repo %s' %
                             (Bcfg2.Options.setup.repository, gitroot))
                return 1

            relpath = Bcfg2.Options.setup.repository[len(gitroot) + 1:]
        else:
            gitroot = Bcfg2.Options.setup.repository
            relpath = ''

        self.logger.info('Using Git repo at %s' % gitroot)

        try:
            repo = git.Repo(gitroot)
        except:  # pylint: disable=W0702
            self.logger.error('Error setting up Git repo at %s: %s' %
                              (gitroot, sys.exc_info()[1]))
            return 1

        new = 0
        changed = 0
        self.logger.debug('Untracked files: %s' % repo.untracked_files)
        for path in repo.untracked_files:
            if self.add_to_commit(repo, path, relpath):
                new += 1
            else:
                self.logger.debug('Not adding %s to commit' % path)

        self.logger.debug('Untracked files after building commit: %s' %
                          repo.untracked_files)

        changes = list_changed_files(repo)
        self.logger.info('Changed files: %s' %
                         [d.a_blob.path for d in changes])

        for diff in changes:
            if self.add_to_commit(repo, diff.a_blob.path, relpath):
                changed += 1
            else:
                self.logger.debug('Not adding %s to commit' %
                                  diff.a_blob.path)
        self.logger.info('Changed files after building commit: %s' %
                         [d.a_blob.path for d in list_changed_files(repo)])

        if new + changed > 0:
            self.logger.debug('Committing %s new files and %s changed files' %
                              (new, changed))

            if Bcfg2.Options.setup.dry_run:
                self.logger.warning('In dry-run mode, skipping commit '
                                    'and push')
            else:
                output = repo.index.commit('Auto-commit with %s from %s run' %
                                           (self.progname,
                                            Bcfg2.Options.setup.hostname))
                if output:
                    self.logger.debug(output)

                if 'origin' in repo.remotes:
                    remote = repo.remote()
                    self.logger.debug('Pushing to remote %s at %s' %
                                      (remote, remote.url))
                    output = remote.push()
                    if output:
                        self.logger.debug(output)
                else:
                    self.logger.info('Not pushing because there is no origin')
        else:
            self.logger.info('No changes to commit')


if __name__ == '__main__':
    sys.exit(CLI().run())
