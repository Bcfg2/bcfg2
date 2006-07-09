<?xml version="1.0"?>

<!-- $Id$ -->

<encap_profile
	profile_ver="1.0"
	pkgspec="bcfg2-openssl-0.9.8b"
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
	url="http://www.openssl.org/source/openssl-0.9.8b.tar.gz"
	use_objdir="no"
>

<configure>
./config \
	--prefix="${ENCAP_SOURCE}/${ENCAP_PKGNAME}/lib/bcfg2" \
	zlib-dynamic shared \
	-L/usr/local/lib/bcfg2/lib \
	-I/usr/local/lib/bcfg2/include
</configure>

</source>

<prepackage>
mkdir bin 2>/dev/null || exit 0
ln -sf ../lib/bcfg2/bin/openssl bin/b2openssl
mkdir var 2>/dev/null || exit 0
mkdir var/encap 2>/dev/null || exit 0
touch var/encap/${ENCAP_PKGNAME}
</prepackage>

<encapinfo>
description SSL encryption tool and library
</encapinfo>

</encap_profile>
