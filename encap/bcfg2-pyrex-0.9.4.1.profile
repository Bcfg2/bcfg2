<?xml version="1.0"?>

<!-- $Id$ -->

<encap_profile
	profile_ver="1.0"
	pkgspec="bcfg2-pyrex-0.9.4.1"
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
url="http://www.pobox.com/users/dclark/mirror/Pyrex-0.9.4.1.tar.gz
     http://www.cosc.canterbury.ac.nz/~greg/python/Pyrex/Pyrex-0.9.4.1.tar.gz"
>

<configure>
:
</configure>

<build>
/usr/local/lib/bcfg2/bin/python setup.py build \
--build-base=${builddir}/build
</build>

<install>
/usr/local/lib/bcfg2/bin/python setup.py install \
--prefix=${ENCAP_SOURCE}/${ENCAP_PKGNAME}/lib/bcfg2 \
</install>

<clean>
/usr/local/lib/bcfg2/bin/python setup.py clean
</clean>

</source>

<prepackage type="set">
chmod -R o+r lib/bcfg2
mkdir var 2>/dev/null || exit 0
mkdir var/encap 2>/dev/null || exit 0
touch var/encap/${ENCAP_PKGNAME}
</prepackage>

<encapinfo>
description Pyrex - a Language for Writing Python Extension Modules
</encapinfo>

</encap_profile>
