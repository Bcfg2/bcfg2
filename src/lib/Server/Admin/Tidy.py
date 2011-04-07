import os
import re
import socket

import Bcfg2.Server.Admin


class Tidy(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = "Clean up useless files in the repo"
    __longhelp__ = __shorthelp__ + "\n\nbcfg2-admin tidy [-f] [-I]\n"
    __usage__ = ("bcfg2-admin tidy [options]\n\n"
                 "     %-25s%s\n"
                 "     %-25s%s\n" %
                ("-f",
                 "force",
                 "-I",
                 "interactive"))

    def __init__(self, cfile):
        Bcfg2.Server.Admin.Mode.__init__(self, cfile)

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        badfiles = self.buildTidyList()
        if '-f' in args or '-I' in args:
            if '-I' in args:
                for name in badfiles[:]:
                    # py3k compatibility
                    try:
                        answer = raw_input("Unlink file %s? [yN] " % name)
                    except NameError:
                        answer = input("Unlink file %s? [yN] " % name)
                    if answer not in ['y', 'Y']:
                        badfiles.remove(name)
            for name in badfiles:
                try:
                    os.unlink(name)
                except IOError:
                    print("Failed to unlink %s" % name)
        else:
            for name in badfiles:
                print(name)

    def buildTidyList(self):
        """Clean up unused or unusable files from the repository."""
        hostmatcher = re.compile('.*\.H_(\S+)$')
        to_remove = []
        good = []
        bad = []

        # clean up unresolvable hosts in SSHbase
        for name in os.listdir("%s/SSHbase" % (self.get_repo_path())):
            if hostmatcher.match(name):
                hostname = hostmatcher.match(name).group(1)
                if hostname in good + bad:
                    continue
                try:
                    socket.gethostbyname(hostname)
                    good.append(hostname)
                except:
                    bad.append(hostname)
        for name in os.listdir("%s/SSHbase" % (self.get_repo_path())):
            if not hostmatcher.match(name):
                to_remove.append("%s/SSHbase/%s" % (self.get_repo_path(),
                                                    name))
            else:
                if hostmatcher.match(name).group(1) in bad:
                    to_remove.append("%s/SSHbase/%s" %
                                    (self.get_repo_path(), name))
        # clean up file~
        # clean up files without parsable names in Cfg
        return to_remove
