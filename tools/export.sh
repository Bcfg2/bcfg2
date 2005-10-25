#!/usr/bin/env sh

version="${1}"

if [ -z "$version" ] ; then
    echo "must supply version number"
    exit 1
fi

bk export . /tmp/bcfg2-${version}
bk changes -aer > /tmp/bcfg2-${version}/ChangeLog
cd /tmp/bcfg2-${version}/doc
make
cd /tmp
tar czf bcfg2-${version}.tar.gz bcfg2-${version}