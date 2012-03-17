#!/usr/bin/python

import os
import Bcfg2.Client.Proxy

if not os.getuid() == 0:
    print("this command must be run as root")
    raise SystemExit

proxy = Bcfg2.Client.Proxy.bcfg2()
print("building files...")
proxy.run_method('Hostbase.rebuildState', ())
print("running bcfg...")
os.system('bcfg2 -q -d -v')
