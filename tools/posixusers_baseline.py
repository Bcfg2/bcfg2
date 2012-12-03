#!/usr/bin/env python

import grp
import sys
import logging
import lxml.etree
import Bcfg2.Logger
from Bcfg2.Client.Tools.POSIXUsers import POSIXUsers
from Bcfg2.Options import OptionParser, Option, get_bool, CLIENT_COMMON_OPTIONS


def get_setup():
    optinfo = CLIENT_COMMON_OPTIONS
    optinfo['nouids'] = Option("Do not include UID numbers for users",
                               default=False,
                               cmd='--no-uids',
                               long_arg=True,
                               cook=get_bool)
    optinfo['nogids'] = Option("Do not include GID numbers for groups",
                               default=False,
                               cmd='--no-gids',
                               long_arg=True,
                               cook=get_bool)
    setup = OptionParser(optinfo)
    setup.parse(sys.argv[1:])

    if setup['args']:
        print("posixuser_[baseline.py takes no arguments, only options")
        print(setup.buildHelpMessage())
        raise SystemExit(1)
    level = 30
    if setup['verbose']:
        level = 20
    if setup['debug']:
        level = 0
    Bcfg2.Logger.setup_logging('posixusers_baseline.py',
                               to_syslog=False,
                               level=level,
                               to_file=setup['logging'])
    return setup


def main():
    setup = get_setup()
    if setup['file']:
        config = lxml.etree.parse(setup['file']).getroot()
    else:
        config = lxml.etree.Element("Configuration")
    users = POSIXUsers(logging.getLogger('posixusers_baseline.py'),
                       setup, config)

    baseline = lxml.etree.Element("Bundle", name="posixusers_baseline")
    for entry in users.FindExtra():
        data = users.existing[entry.tag][entry.get("name")]
        for attr, idx in users.attr_mapping[entry.tag].items():
            if (entry.get(attr) or
                (attr == 'uid' and setup['nouids']) or
                (attr == 'gid' and setup['nogids'])):
                continue
            entry.set(attr, str(data[idx]))
        if entry.tag == 'POSIXUser':
            entry.set("group", grp.getgrgid(data[3])[0])
            for group in users.user_supplementary_groups(entry):
                memberof = lxml.etree.SubElement(entry, "MemberOf")
                memberof.text = group[0]

        entry.tag = "Bound" + entry.tag
        baseline.append(entry)

    print(lxml.etree.tostring(baseline, pretty_print=True))

if __name__ == "__main__":
    sys.exit(main())
