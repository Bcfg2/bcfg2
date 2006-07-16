<?xml version="1.0"?>

<!-- $Id$ -->

<encap_profile
	profile_ver="1.0"
	pkgspec="bcfg2-zlib-1.2.3"
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
	url="http://www.pobox.com/users/dclark/mirror/zlib-1.2.3.tar.gz
	     http://www.zlib.net/zlib-1.2.3.tar.gz"
>

<configure>
./configure \
PLATFORM_IF_MATCH(aix)
PLATFORM_ELSE
	--shared \
PLATFORM_ENDIF
	--prefix="${ENCAP_SOURCE}/${ENCAP_PKGNAME}/lib/bcfg2"
</configure>

</source>

<prepackage type="set">
mkdir var 2>/dev/null || exit 0
mkdir var/encap 2>/dev/null || exit 0
touch var/encap/${ENCAP_PKGNAME}
</prepackage>

<encapinfo>
description Zlib compression library
</encapinfo>

</encap_profile>
