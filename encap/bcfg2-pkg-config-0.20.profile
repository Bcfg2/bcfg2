<?xml version="1.0"?>

<!-- $Id$ -->

<encap_profile
	profile_ver="1.0"
	pkgspec="bcfg2-pkg-config-0.20"
>

<environment
        variable="CC"
        value="gcc"
        type="set"
/>

<environment
        variable="PATH"
PLATFORM_IF_MATCH(solaris)
        value="/usr/local/lib/bcfg2/bin:/usr/local/bin:/usr/sfw/bin:/usr/ccs/bin:"
PLATFORM_ELSE
        value="/usr/local/lib/bcfg2/bin:/usr/local/bin:"
PLATFORM_ENDIF
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
PLATFORM_ELSE_IF_MATCH(solaris)
        value="-L/usr/local/lib/bcfg2/lib -R/usr/local/lib/bcfg2/lib:/usr/lib -YP,/usr/local/lib/bcfg2/lib:/usr/lib"
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
url="http://www.pobox.com/users/dclark/mirror/pkg-config-0.20.tar.gz
     http://pkgconfig.freedesktop.org/releases/pkg-config-0.20.tar.gz"
>

<configure>
./configure \
	--prefix="${ENCAP_SOURCE}/${ENCAP_PKGNAME}/lib/bcfg2" \
	--with-pc-path=/usr/local/lib/bcfg2/lib/pkgconfig
</configure>

</source>

<prepackage type="set">
mkdir var 2>/dev/null || exit 0
mkdir var/encap 2>/dev/null || exit 0
touch var/encap/${ENCAP_PKGNAME}
</prepackage>

<encapinfo>
description pkg-config - application and library compilation helper tool
</encapinfo>

</encap_profile>
