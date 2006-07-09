<?xml version="1.0"?>

<!-- $Id$ -->

<encap_profile
	profile_ver="1.0"
	pkgspec="bcfg2-libxslt-1.1.17"
>

<environment
        variable="CC"
        value="gcc"
        type="set"
/>

<environment
        variable="PATH"
        value="/usr/local/lib/bcfg2/bin:/usr/local/bin:"
        type="prepend"
/>

PLATFORM_IF_MATCH(linux)
PLATFORM_ELSE
<environment
        variable="MAKE"
        value="gmake"
        type="set"
/>
PLATFORM_ENDIF

<environment
        variable="LDFLAGS"
PLATFORM_IF_MATCH(linux)
        value="-L/usr/local/lib/bcfg2/lib -Wl,-rpath,/usr/local/lib/bcfg2/lib"
PLATFORM_ELSE_IF_MATCH(aix)
        value="-L/usr/local/lib/bcfg2/lib -Wl,-blibpath:/usr/local/lib/bcfg2/lib:/usr/lib"
PLATFORM_ELSE
PLATFORM_ENDIF
        type="set"
/>

<environment
        variable="CPPFLAGS"
        value="-I/usr/local/lib/bcfg2/include"
        type="set"
/>

<source
	url="ftp://xmlsoft.org/libxml2/libxslt-1.1.17.tar.gz"
>

<configure>
./configure \
	--prefix="${ENCAP_SOURCE}/${ENCAP_PKGNAME}/lib/bcfg2" \
PLATFORM_IF_MATCH(aix)
PLATFORM_ELSE
	--enable-shared \
PLATFORM_ENDIF
	--with-crypto=no \
	--with-libxml-prefix=/usr/local/lib/bcfg2 \
	--with-libxml-include-prefix=/usr/local/lib/bcfg2/include \
	--with-libxml-libs-prefix=/usr/local/lib/bcfg2/lib \
	--enable-ipv6=no \
	--with-python=/usr/local/lib/bcfg2 \
	--with-zlib=/usr/local/lib/bcfg2
</configure>

</source>

<prepackage type="set">
mv lib/bcfg2/lib/lib/python2.4 lib/bcfg2/lib
rmdir lib/bcfg2/lib/lib
mkdir var 2>/dev/null || exit 0
mkdir var/encap 2>/dev/null || exit 0
touch var/encap/${ENCAP_PKGNAME}
</prepackage>

<encapinfo>
description Libxml2 - XML C library for the Gnome project
</encapinfo>

</encap_profile>
