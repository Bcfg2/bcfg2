#!/usr/bin/env python
""" Trigger script to commit selected changes to a local repository
back to git.  To use this script, enable the Trigger plugin, put this
script in /var/lib/bcfg2/Trigger/, and create /etc/bcfg2-commit.conf.

The config file, /etc/bcfg2-commit.conf, may contain four options in
the [global] section:

* "config" is the path to the Bcfg2 server config file.  (Default:
  /etc/bcfg2.conf)
* "commit" is a comma-separated list of globs giving the paths that
  should be committed back to the repository.  Default is 'SSLCA/*,
  SSHbase/*, Cfg/*', which will commit data back for SSLCA, SSHbase,
  Cfg, FileProbes, etc., but not, for instance, Probes/probed.xml.
  You may wish to add Metadata/clients.xml to the commit list.
* "debug" and "verbose" let you set the log level for git_commit.py
  itself.
"""


import os
import sys
import git
import logging
import Bcfg2.Logger
import Bcfg2.Options
from Bcfg2.Compat import ConfigParser
from fnmatch import fnmatch

# config file path
CONFIG = "/etc/bcfg2-commit.conf"

# config defaults.  all config options are in the [global] section
DEFAULTS = dict(config='/etc/bcfg2.conf',
                commit="SSLCA/*, SSHbase/*, Cfg/*")


def list_changed_files(repo):
    return [d for d in repo.index.diff(None)
            if (d.a_blob is not None and not d.deleted_file and
                not d.renamed and not d.new_file)]


def add_to_commit(patterns, path, repo, relpath):
    progname = os.path.basename(sys.argv[0])
    logger = logging.getLogger(progname)
    for pattern in patterns:
        if fnmatch(path, os.path.join(relpath, pattern)):
            logger.debug("%s: Adding %s to commit" % (progname, path))
            repo.index.add([path])
            return True
    return False


def parse_options():
    config = ConfigParser.SafeConfigParser(DEFAULTS)
    config.read(CONFIG)

    optinfo = dict(
        profile=Bcfg2.Options.CLIENT_PROFILE,
        dryrun=Bcfg2.Options.CLIENT_DRYRUN,
        groups=Bcfg2.Options.Option("Groups",
                                    default=[],
                                    cmd="-g",
                                    odesc='<group>:<group>',
                                    cook=Bcfg2.Options.colon_split))
    optinfo.update(Bcfg2.Options.CLI_COMMON_OPTIONS)
    optinfo.update(Bcfg2.Options.SERVER_COMMON_OPTIONS)
    argv = [Bcfg2.Options.CFILE.cmd, config.get("global", "config")]
    argv.extend(sys.argv[1:])
    setup = Bcfg2.Options.OptionParser(optinfo, argv=argv)
    setup.parse(argv)

    setup['commit'] = Bcfg2.Options.list_split(config.get("global",
                                                          "commit"))
    for opt in ['debug', 'verbose']:
        try:
            setup[opt] = config.getboolean("global", opt)
        except ConfigParser.NoOptionError:
            pass

    try:
        hostname = setup['args'][0]
    except IndexError:
        print(setup.hm)
        raise SystemExit(1)
    return (setup, hostname)


def setup_logging(setup):
    progname = os.path.basename(sys.argv[0])
    log_args = dict(to_syslog=setup['syslog'], to_console=sys.stdout.isatty(),
                    to_file=setup['logging'], level=logging.WARNING)
    if setup['debug']:
        log_args['level'] = logging.DEBUG
    elif setup['verbose']:
        log_args['level'] = logging.INFO
    Bcfg2.Logger.setup_logging(progname, **log_args)
    return logging.getLogger(progname)


def main():
    progname = os.path.basename(sys.argv[0])
    setup, hostname = parse_options()
    logger = setup_logging(setup)
    if setup['dryrun']:
        logger.info("%s: In dry-run mode, changes will not be committed" %
                    progname)

    if setup['vcs_root']:
        gitroot = os.path.realpath(setup['vcs_root'])
    else:
        gitroot = os.path.realpath(setup['repo'])
    logger.info("%s: Using Git repo at %s" % (progname, gitroot))
    try:
        repo = git.Repo(gitroot)
    except:  # pylint: disable=W0702
        logger.error("%s: Error setting up Git repo at %s: %s" %
                     (progname, gitroot, sys.exc_info()[1]))
        return 1

    # canonicalize the repo path so that git will recognize it as
    # being inside the git repo
    bcfg2root = os.path.realpath(setup['repo'])

    if not bcfg2root.startswith(gitroot):
        logger.error("%s: Bcfg2 repo %s is not inside Git repo %s" %
                     (progname, bcfg2root, gitroot))
        return 1

    # relative path to Bcfg2 root from VCS root
    if gitroot == bcfg2root:
        relpath = ''
    else:
        relpath = bcfg2root[len(gitroot) + 1:]

    new = 0
    changed = 0
    logger.debug("%s: Untracked files: %s" % (progname, repo.untracked_files))
    for path in repo.untracked_files:
        if add_to_commit(setup['commit'], path, repo, relpath):
            new += 1
        else:
            logger.debug("%s: Not adding %s to commit" % (progname, path))
    logger.debug("%s: Untracked files after building commit: %s" %
                 (progname, repo.untracked_files))

    changes = list_changed_files(repo)
    logger.info("%s: Changed files: %s" % (progname,
                                           [d.a_blob.path for d in changes]))
    for diff in changes:
        if add_to_commit(setup['commit'], diff.a_blob.path, repo, relpath):
            changed += 1
        else:
            logger.debug("%s: Not adding %s to commit" % (progname,
                                                          diff.a_blob.path))
    logger.info("%s: Changed files after building commit: %s" %
                (progname, [d.a_blob.path for d in list_changed_files(repo)]))

    if new + changed > 0:
        logger.debug("%s: Committing %s new files and %s changed files" %
                     (progname, new, changed))
        if setup['dryrun']:
            logger.warning("%s: In dry-run mode, skipping commit and push" %
                           progname)
        else:
            output = repo.index.commit("Auto-commit with %s from %s run" %
                                       (progname, hostname))
            if output:
                logger.debug("%s: %s" % (progname, output))
            remote = repo.remote()
            logger.debug("%s: Pushing to remote %s at %s" % (progname, remote,
                                                             remote.url))
            output = remote.push()
            if output:
                logger.debug("%s: %s" % (progname, output))
    else:
        logger.info("%s: No changes to commit" % progname)

if __name__ == '__main__':
    sys.exit(main())
