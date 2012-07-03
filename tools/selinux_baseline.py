#!/usr/bin/env python

import sys
import logging
import lxml.etree

import Bcfg2.Logger
import Bcfg2.Options
from Bcfg2.Client.Tools.SELinux import *

LOGGER = None

def get_setup():
    global LOGGER
    optinfo = Bcfg2.Options.CLIENT_COMMON_OPTIONS
    setup = Bcfg2.Options.OptionParser(optinfo)
    setup.parse(sys.argv[1:])

    if setup['args']:
        print("selinux_baseline.py takes no arguments, only options")
        print(setup.buildHelpMessage())
        raise SystemExit(1)
    level = 30
    if setup['verbose']:
        level = 20
    if setup['debug']:
        level = 0
    Bcfg2.Logger.setup_logging('selinux_base',
                               to_syslog=False,
                               level=level,
                               to_file=setup['logging'])
    LOGGER = logging.getLogger('bcfg2')
    return setup

def main():
    setup = get_setup()
    config = lxml.etree.Element("Configuration")
    selinux = SELinux(LOGGER, setup, config)

    baseline = lxml.etree.Element("Bundle", name="selinux_baseline")
    for etype, handler in selinux.handlers.items():
        baseline.append(lxml.etree.Comment("%s entries" % etype))
        extra = handler.FindExtra()
        for entry in extra:
            entry.tag = "BoundSELinux"
        baseline.extend(extra)

    print lxml.etree.tostring(baseline, pretty_print=True)

if __name__ == "__main__":
    sys.exit(main())
