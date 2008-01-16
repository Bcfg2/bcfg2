#!/usr/bin/env sh

name="bcfg2"
repo="https://svn.mcs.anl.gov/repos/bcfg"
version="${1}"
expath="/tmp/${name}-${version}/"
tarname="/tmp/${name}-${version}.tar.gz"
url=`svn info | grep URL | awk '{print $2}'`

if [ -z "$version" ] ; then
    echo "must supply version number"
    exit 1
fi
tagstr=`echo ${version} | sed -e 's/\./_/g'`
svn copy "$url" "${repo}/tags/${name}_${tagstr}" -m "tagged ${version} release"
svn export . "${expath}"
svn log -v "${repo}/tags/${name}_${tagstr}" > "${expath}/ChangeLog"
cd /tmp

tar czf "${tarname}" "${name}-${version}"
gpg --armor --output "${tarname}".gpg --detach-sig "${tarname}"
scp "${tarname}"* terra.mcs.anl.gov:/nfs/ftp/pub/bcfg

