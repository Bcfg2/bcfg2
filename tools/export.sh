#!/usr/bin/env sh

version="${1}"

if [ -z "$version" ] ; then
    echo "must supply version number"
    exit 1
fi
tagstr=`echo ${version} | sed -e 's/\./_/g'`
svn copy svn+ssh://terra.mcs.anl.gov/home/desai/svn/bcfg/trunk svn+ssh://terra.mcs.anl.gov/home/desai/svn/bcfg/tags/bcfg2_${tagstr}
svn export . /tmp/bcfg2-${version}
svn log -v > /tmp/bcfg2-${version}/ChangeLog
cd /tmp/bcfg2-${version}/doc
make
cd /tmp
filename="/tmp/bcfg2-${version}.tar.gz"
tar czf "${filename}" bcfg2-${version}
gpg --armor --output "${filename}".gpg --detach-sig "${filename}"
scp /tmp/bcfg2-${version}.tar.gz* terra.mcs.anl.gov:/nfs/ftp/pub/bcfg
scp /tmp/bcfg2-${version}.tar.gz* terra.mcs.anl.gov:/nfs/www-space-004/cobalt/bcfg2
