#!/usr/bin/env python

import os
import sys
from Bcfg2.Compat import ConfigParser
import Bcfg2.Options


def copy_section(src_file, tgt_cfg, section, newsection=None):
    if newsection is None:
        newsection = section

    cfg = ConfigParser.ConfigParser()
    if len(cfg.read(src_file)) == 1:
        if cfg.has_section(section):
            try:
                tgt_cfg.add_section(newsection)
            except ConfigParser.DuplicateSectionError:
                print("[%s] section already exists in %s, adding options" %
                      (newsection, Bcfg2.Options.setup.config))
            for opt in cfg.options(section):
                val = cfg.get(section, opt)
                if tgt_cfg.has_option(newsection, opt):
                    print("%s in [%s] already populated in %s, skipping" %
                          (opt, newsection, Bcfg2.Options.setup.config))
                    print("  %s: %s" % (Bcfg2.Options.setup.config,
                                        tgt_cfg.get(newsection, opt)))
                    print("  %s: %s" % (src_file, val))
                else:
                    print("Set %s in [%s] to %s" % (opt, newsection, val))
                    tgt_cfg.set(newsection, opt, val)

def main():
    parser = Bcfg2.Options.get_parser(
        description="Migrate from Bcfg2 1.2 per-plugin config files to 1.3 "
        "unified config file")
    parser.add_options([Bcfg2.Options.Common.repository])
    parser.parse()
    repo = Bcfg2.Options.setup.repository
    cfp = ConfigParser.ConfigParser()
    cfp.read(Bcfg2.Options.setup.config)

    # files that you should remove manually
    remove = []

    # move rules config out of rules.conf and into bcfg2.conf
    rules_conf = os.path.join(repo, 'Rules', 'rules.conf')
    if os.path.exists(rules_conf):
        remove.append(rules_conf)
        copy_section(rules_conf, cfp, "rules")

    # move packages config out of packages.conf and into bcfg2.conf
    pkgs_conf = os.path.join(repo, 'Packages', 'packages.conf')
    if os.path.exists(pkgs_conf):
        remove.append(pkgs_conf)
        copy_section(pkgs_conf, cfp, "global", newsection="packages")
        for section in ["apt", "yum", "pulp"]:
            copy_section(pkgs_conf, cfp, section,
                         newsection="packages:" + section)

    # move reports database config into [database] section
    if cfp.has_section("statistics"):
        if not cfp.has_section("database"):
            cfp.add_section("database")
        for opt in cfp.options("statistics"):
            if opt.startswith("database_"):
                newopt = opt[9:]
                if cfp.has_option("database", newopt):
                    print("%s in [database] already populated, skipping" %
                          newopt)
                else:
                    cfp.set("database", newopt, cfp.get("statistics", opt))
                    cfp.remove_option("statistics", opt)

    print("Writing %s" % Bcfg2.Options.setup.config)
    try:
        cfp.write(open(Bcfg2.Options.setup.config, "w"))
        if len(remove):
            print("Settings were migrated, but you must remove these files "
                  "manually:")
            for path in remove:
                print("  %s" % path)
    except IOError:
        err = sys.exc_info()[1]
        print("Could not write %s: %s" % (Bcfg2.Options.setup.config, err))

if __name__ == '__main__':
    sys.exit(main())
