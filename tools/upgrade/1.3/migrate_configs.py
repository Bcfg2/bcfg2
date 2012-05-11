#!/usr/bin/env python

import os
import sys
from Bcfg2.Bcfg2Py3k import ConfigParser
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
                      (newsection, setup['cfile']))
            for opt in cfg.options(section):
                val = cfg.get(section, opt)
                if tgt_cfg.has_option(newsection, opt):
                    print("%s in [%s] already populated in %s, skipping" %
                          (opt, newsection, setup['cfile']))
                    print("  %s: %s" % (setup['cfile'],
                                        tgt_cfg.get(newsection, opt)))
                    print("  %s: %s" % (src_file, val))
                else:
                    print("Set %s in [%s] to %s" % (opt, newsection, val))
                    tgt_cfg.set(newsection, opt, val)

def main():
    opts = dict(repo=Bcfg2.Options.SERVER_REPOSITORY,
                configfile=Bcfg2.Options.CFILE)
    setup = Bcfg2.Options.OptionParser(opts)
    setup.parse(sys.argv[1:])

    copy_section(os.path.join(setup['repo'], 'Rules', 'rules.conf'), setup.cfp,
                 "rules")
    pkgs_conf = os.path.join(setup['repo'], 'Packages', 'packages.conf')
    copy_section(pkgs_conf, setup.cfp, "global", newsection="packages")
    for section in ["apt", "yum", "pulp"]:
        copy_section(pkgs_conf, setup.cfp, section,
                     newsection="packages:" + section)

    print("Writing %s" % setup['configfile'])
    try:
        setup.cfp.write(open(setup['configfile'], "w"))
    except IOError:
        err = sys.exc_info()[1]
        print("Could not write %s: %s" % (setup['configfile'], err))

if __name__ == '__main__':
    sys.exit(main())
