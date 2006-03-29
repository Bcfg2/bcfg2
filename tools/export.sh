#!/usr/bin/env sh

name="bcfg2"
repo="https://svn.mcs.anl.gov/repos/bcfg2"
version="${1}"
expath="/tmp/${name}-${version}/"
tarname="/tmp/${name}-${version}.tar.gz"

if [ -z "$version" ] ; then
    echo "must supply version number"
    exit 1
fi
tagstr=`echo ${version} | sed -e 's/\./_/g'`
svn copy "${repo}/trunk" "${repo}/tags/${name}_${tagstr}" -m "tagged ${version} release"
svn export . "${expath}"
svn log -v "${repo}/tags/${name}_${tagstr}" > "${expath}/ChangeLog"
cd "${expath}"/doc && make
cd /tmp

tar czf "${tarname}" "${name}-${version}"
gpg --armor --output "${tarname}".gpg --detach-sig "${tarname}"
scp "${tarname}"* terra.mcs.anl.gov:/nfs/ftp/pub/bcfg

