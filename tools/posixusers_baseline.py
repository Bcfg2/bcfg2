#!/usr/bin/env python

import grp
import sys
import logging
import lxml.etree
import Bcfg2.Logger
import Bcfg2.Options
from Bcfg2.Client.Tools.POSIXUsers import POSIXUsers


class CLI(object):
    options = [
        Bcfg2.Options.BooleanOption(
            "--no-uids", help="Do not include UID numbers for users"),
        Bcfg2.Options.BooleanOption(
            "--no-gids", help="Do not include GID numbers for groups")]

    def __init__(self):
        Bcfg2.Options.get_parser(
            description="Generate a bundle with a baseline of POSIX users and "
            "groups",
            components=[self, POSIXUsers]).parse()
        config = lxml.etree.Element("Configuration")
        self.users = POSIXUsers(config)
        self.logger = logging.getLogger('posixusers_baseline.py')

    def run(self):
        baseline = lxml.etree.Element("Bundle", name="posixusers_baseline")
        for entry in self.users.FindExtra():
            data = self.users.existing[entry.tag][entry.get("name")]
            for attr, idx in self.users.attr_mapping[entry.tag].items():
                if (entry.get(attr) or
                    (attr == 'uid' and Bcfg2.Options.setup.no_uids) or
                    (attr == 'gid' and Bcfg2.Options.setup.no_gids)):
                    continue
                entry.set(attr, str(data[idx]))
            if entry.tag == 'POSIXUser':
                try:
                    entry.set("group", grp.getgrgid(data[3])[0])
                except KeyError:
                    self.logger.warning(
                        "User %s is a member of nonexistent group %s" %
                        (entry.get("name"), data[3]))
                    entry.set("group", str(data[3]))
                for group in self.users.user_supplementary_groups(entry):
                    lxml.etree.SubElement(entry, "MemberOf", group=group[0])

            entry.tag = "Bound" + entry.tag
            baseline.append(entry)

        print(lxml.etree.tostring(baseline, pretty_print=True))

if __name__ == "__main__":
    sys.exit(CLI().run())
