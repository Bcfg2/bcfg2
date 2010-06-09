#!/usr/bin/env sh

name="bcfg2"
repo="https://svn.mcs.anl.gov/repos/bcfg"
version="${1}"
expath="/tmp/${name}-${version}/"
tarname="/tmp/${name}-${version}.tar.gz"
url=`svn info | grep URL | awk '{print $2}'`

if [ -z "${version}" ] ; then
    echo "Usage: $0 <version>"
    exit 1
fi

# update the version
tmpbase=`basename $0`
deblogtmp=`mktemp /tmp/${tmpbase}.XXXXXX`
majorver=`/usr/bin/python -c "print '${version}'[:5]"`
minorver=`/usr/bin/python -c "print '${version}'[5:]"`
printf "name: "
read name
printf "email: "
read email
cat > deblogtmp << EOF
bcfg2 (${majorver}-0.0${minorver}) unstable; urgency=low

  * New upstream release

 -- ${name} <${email}>  `/bin/date -R`

EOF
sed -i "s/^\(Version:\)          [:digits:]*.*$/\1          ${version}/" misc/bcfg2.spec
cat debian/changelog >> deblogtmp
mv deblogtmp debian/changelog
echo ${majorver} > redhat/VERSION
echo 0.0${minorver} > redhat/RELEASE
sed -i "s/\(version=\).*/\1\"${version}\",/" setup.py
sed -i "s/^\(VERS\).*/\1=${version}-1/" solaris/Makefile
svn ci -m "Version bump to ${version}"

# tag the release
tagstr=`echo ${version} | sed -e 's/\./_/g'`
svn copy "$url" "${repo}/tags/${name}_${tagstr}" -m "tagged ${version} release"
svn export . "${expath}"
svn log -v "${repo}/tags/${name}_${tagstr}" > "${expath}/ChangeLog"
cd /tmp

tar czf "${tarname}" "${name}-${version}"
gpg --armor --output "${tarname}".gpg --detach-sig "${tarname}"
scp "${tarname}"* terra.mcs.anl.gov:/mcs/ftp/pub/bcfg
