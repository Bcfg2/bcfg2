#!/bin/bash
# $Id$

ENCAP_PKGNAME="m4-1.4.4"
PATH="$PATH:/usr/local/bin"
export PATH

date > ${ENCAP_PKGNAME}.log

if [ -f "${ENCAP_PKGNAME}.ep" ]; then rm ${ENCAP_PKGNAME}.ep; fi
cat > ${ENCAP_PKGNAME}.ep << EOF
<?xml version="1.0"?>

<encap_profile
	profile_ver="1.0"
	pkgspec="m4-1.4.4"
>

<environment
        variable="CC"
        value="gcc"
        type="set"
/>

<environment
        variable="PATH"
        value="/usr/local/bin:"
        type="prepend"
/>

<environment
        variable="PATH"
        value=":/usr/sfw/bin:/usr/ccs/bin"
        type="append"
/>

<source
url="http://encapsrcdist/mirror/m4/m4-1.4.4.tar.gz
     http://mirror.opensysadmin.com/m4/m4-1.4.4.tar.gz
     http://ftp.gnu.org/gnu/m4/m4-1.4.4.tar.gz"
>

</source>

<prepackage type="set">
test -d var || mkdir var
test -d var/encap || mkdir var/encap
touch var/encap/${ENCAP_PKGNAME}
</prepackage>

<encapinfo>
description m4 - GNU implementation of the traditional Unix macro processor
</encapinfo>

</encap_profile>
EOF

if [ -f m4-fake ]; then rm m4-fake; fi
cat > m4-fake << EOF
#!/bin/sh
cat \$4
EOF
chmod 755 m4-fake

CURDIR="`pwd`"

printf "Environment variables:\n" \
	>> ${ENCAP_PKGNAME}.log
env >> ${ENCAP_PKGNAME}.log

printf "\nsrcdir:|%s| pwd:|%s| \$0:|%s|\n" "${srcdir}" "`pwd`" "$0" \
    >> ${ENCAP_PKGNAME}.log

printf "\n%s :\n" "`ls -l ${ENCAP_PKGNAME}.ep`" \
    >> ${ENCAP_PKGNAME}.log
cat ${ENCAP_PKGNAME}.ep >> ${ENCAP_PKGNAME}.log

printf "\n\n%s :\n" "`ls -l m4-fake`" \
    >> ${ENCAP_PKGNAME}.log
cat m4-fake >> ${ENCAP_PKGNAME}.log

printf "\n${MKENCAP} -m ${CURDIR}/m4-fake -b -DUP ${ENCAP_PKGNAME}.ep :\n" \
    >> ${ENCAP_PKGNAME}.log
( ${MKENCAP} -m ${CURDIR}/m4-fake -b -DUP ${ENCAP_PKGNAME}.ep || true ) \
    >> ${ENCAP_PKGNAME}.log 2>&1

printf "\n${MKENCAP} -m ${CURDIR}/m4-fake -b -T ${ENCAP_PKGNAME}.ep :\n" \
    >> ${ENCAP_PKGNAME}.log
( ${MKENCAP} -m ${CURDIR}/m4-fake -b -T ${ENCAP_PKGNAME}.ep || true ) \
    >> ${ENCAP_PKGNAME}.log 2>&1

printf "\n${MKENCAP} -m ${CURDIR}/m4-fake -b -CBI ${ENCAP_PKGNAME}.ep :\n" \
    >> ${ENCAP_PKGNAME}.log
( ${MKENCAP} -m ${CURDIR}/m4-fake -b -CBI ${ENCAP_PKGNAME}.ep ) \
    >> ${ENCAP_PKGNAME}.log 2>&1

rm m4-fake >> ${ENCAP_PKGNAME}.log 2>&1
rm ${ENCAP_PKGNAME}.ep >> ${ENCAP_PKGNAME}.log 2>&1

exit 0
