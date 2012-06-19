#!/bin/sh
cd build
PP="./lib/python/site-packages/"

#bcfg2
echo "i pkginfo=./pkginfo.bcfg2" >  ../prototype.tmp
find . | grep man[15] | pkgproto >> ../prototype.tmp
echo "./bin"  | pkgproto >> ../prototype.tmp
echo "./bin/bcfg2"  | pkgproto >> ../prototype.tmp
echo "${PP}Bcfg2" | pkgproto >> ../prototype.tmp
ls -1 ${PP}Bcfg2/*.py  | pkgproto >> ../prototype.tmp
find  ${PP}Bcfg2/Client/ ! -name "*.pyc"  | pkgproto >> ../prototype.tmp
sed "s/`id | sed 's/uid=[0-9]*(\(.*\)) gid=[0-9]*(\(.*\))/\1 \2/'`/bin bin/" ../prototype.tmp > ../prototype.bcfg2

#bcfg2-server
echo "i pkginfo=./pkginfo.bcfg2-server" >  ../prototype.tmp
find . | grep man8 | pkgproto >> ../prototype.tmp
find share/bcfg2 | pkgproto >> ../prototype.tmp
echo "./bin"  | pkgproto >> ../prototype.tmp
ls -1 bin/bcfg2-* | pkgproto >> ../prototype.tmp
find  ${PP}Bcfg2/Server/ ! -name "*.pyc"  | pkgproto >> ../prototype.tmp
sed "s/`id | sed 's/uid=[0-9]*(\(.*\)) gid=[0-9]*(\(.*\))/\1 \2/'`/bin bin/" ../prototype.tmp > ../prototype.bcfg2-server

rm ../prototype.tmp
