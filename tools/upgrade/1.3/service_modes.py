#!/usr/bin/env python

import os
import sys
import glob
import lxml.etree
import Bcfg2.Options


def main():
    parser = Bcfg2.Options.get_parser(
        description="Migrate from Bcfg2 1.2 Service modes to 1.3-style "
        "granular Service specification")
    parser.add_options([Bcfg2.Options.Common.repository])
    parser.parse()

    files = []
    for plugin in ['Bundler', 'Rules', 'Default']:
        files.extend(glob.glob(os.path.join(Bcfg2.Options.setup.repository,
                                            plugin, "*")))

    for bfile in files:
        bdata = lxml.etree.parse(bfile)
        changed = False
        for svc in bdata.xpath("//Service|//BoundService"):
            if "mode" not in svc.attrib:
                continue
            mode = svc.get("mode")
            del svc.attrib["mode"]
            if mode not in ["default", "supervised", "interactive_only",
                            "manual"]:
                print("Unrecognized mode on Service:%s: %s.  Assuming default" %
                      (svc.get("name"), mode))
                mode = "default"
            if mode == "default" or mode == "supervised":
                svc.set("restart", "true")
                svc.set("install", "true")
            elif mode == "interactive_only":
                svc.set("restart", "interactive")
                svc.set("install", "true")
            elif mode == "manual":
                svc.set("restart", "false")
                svc.set("install", "false")
            changed = True
        if changed:
            print("Writing %s" % bfile)
            try:
                open(bfile, "w").write(lxml.etree.tostring(bdata))
            except IOError:
                err = sys.exc_info()[1]
                print("Could not write %s: %s" % (bfile, err))

if __name__ == '__main__':
    sys.exit(main())
