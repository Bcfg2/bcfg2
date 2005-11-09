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
gpg --sign /tmp/bcfg2-${version}.tar.gz
scp /tmp/bcfg2-${version}.tar.gz* terra.mcs.anl.gov:/nfs/ftp/pub/bcfg
scp /tmp/bcfg2-${version}.tar.gz* terra.mcs.anl.gov:/nfs/www-space-004/cobalt/bcfg2
