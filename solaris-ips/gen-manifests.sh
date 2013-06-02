#!/usr/bin/sh

#bcfg2
cat MANIFEST.bcfg2.header > MANIFEST.bcfg2
pkgsend generate build | grep man[15] >> MANIFEST.bcfg2
pkgsend generate build | grep  Bcfg2/[^/]*.py$ >> MANIFEST.bcfg2
pkgsend generate build | grep  Bcfg2/Client/.*.py$ >> MANIFEST.bcfg2

#bcfg2-server
cat MANIFEST.bcfg2-server.header > MANIFEST.bcfg2-server
pkgsend generate build | grep man[8] >> MANIFEST.bcfg2-server
pkgsend generate build | grep share/bcfg2 >> MANIFEST.bcfg2-server
pkgsend generate build | grep bin/bcfg2- >> MANIFEST.bcfg2-server
pkgsend generate build | grep  Bcfg2/Server/.*.py$ >> MANIFEST.bcfg2-server

