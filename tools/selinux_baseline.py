#!/usr/bin/env python

import sys
import lxml.etree
import Bcfg2.Logger
import Bcfg2.Options
from Bcfg2.Client.Tools.SELinux import SELinux


def main():
    Bcfg2.Options.get_parser(
        description="Get a baseline bundle of SELinux entries",
        components=[SELinux]).parse()
    config = lxml.etree.Element("Configuration")
    selinux = SELinux(config)

    baseline = lxml.etree.Element("Bundle", name="selinux_baseline")
    for etype, handler in selinux.handlers.items():
        baseline.append(lxml.etree.Comment("%s entries" % etype))
        extra = handler.FindExtra()
        for entry in extra:
            if etype != "SEModule":
                entry.tag = "Bound%s" % etype
            else:
                entry.tag = "%s" % etype
        baseline.extend(extra)

    print(lxml.etree.tostring(baseline, pretty_print=True))

if __name__ == "__main__":
    sys.exit(main())
