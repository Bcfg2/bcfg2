#!/bin/sh
# $Id$

ENCAP_PKGNAME=m4-1.4.4
PATH=$PATH:/usr/local/bin
export PATH

cat > ${ENCAP_PKGNAME}.profile << EOF
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

<source
	url="http://www.pobox.com/users/dclark/mirror/m4-1.4.4.tar.gz
	     http://ftp.gnu.org/gnu/m4/m4-1.4.4.tar.gz"
>

</source>

<prepackage type="set">
mkdir var 2>/dev/null || exit 0
mkdir var/encap 2>/dev/null || exit 0
touch var/encap/${ENCAP_PKGNAME}
</prepackage>

<encapinfo>
description m4 - GNU implementation of the traditional Unix macro processor
</encapinfo>

</encap_profile>
EOF

cat > m4-fake << EOF
#!/bin/sh
cat \$4
EOF

chmod 755 m4-fake

( ${MKENCAP} -m ${PWD}/m4-fake -b -DUP ${ENCAP_PKGNAME}.profile || true ) \
	> ${ENCAP_PKGNAME}.log 2>&1

( ${MKENCAP} -m ${PWD}/m4-fake -b -T ${ENCAP_PKGNAME}.profile || true ) \
	>> ${ENCAP_PKGNAME}.log 2>&1

( ${MKENCAP} -m ${PWD}/m4-fake -b -CBI ${ENCAP_PKGNAME}.profile ) \
	>> ${ENCAP_PKGNAME}.log 2>&1

rm m4-fake
rm ${ENCAP_PKGNAME}.profile

exit 0
