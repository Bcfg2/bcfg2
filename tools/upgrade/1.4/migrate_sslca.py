#!/usr/bin/env python

import os
import sys
import shutil
import Bcfg2.Options


def main():
    parser = Bcfg2.Options.get_parser(
        description="Migrate from the SSLCA plugin to built-in Cfg SSL cert "
        "generation")
    parser.add_options([Bcfg2.Options.Common.repository])
    parser.parse()

    sslcadir = os.path.join(Bcfg2.Options.setup.repository, 'SSLCA')
    cfgdir = os.path.join(Bcfg2.Options.setup.repository, 'Cfg')
    for root, _, files in os.walk(sslcadir):
        if not files:
            continue
        newpath = cfgdir + root[len(sslcadir):]
        if not os.path.exists(newpath):
            print("Creating %s and copying contents from %s" % (newpath, root))
            shutil.copytree(root, newpath)
        else:
            print("Copying contents from %s to %s" % (root, newpath))
            for fname in files:
                newfpath = os.path.exists(os.path.join(newpath, fname))
                if newfpath:
                    print("%s already exists, skipping" % newfpath)
                else:
                    shutil.copy(os.path.join(root, fname), newpath)
        cert = os.path.join(newpath, "cert.xml")
        newcert = os.path.join(newpath, "sslcert.xml")
        key = os.path.join(newpath, "key.xml")
        newkey = os.path.join(newpath, "sslkey.xml")
        if os.path.exists(cert):
            os.rename(cert, newcert)
        if os.path.exists(key):
            os.rename(key, newkey)


if __name__ == '__main__':
    sys.exit(main())
