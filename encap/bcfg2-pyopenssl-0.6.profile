<?xml version="1.0"?>

<!-- $Id$ -->

<encap_profile
	profile_ver="1.0"
	pkgspec="bcfg2-pyopenssl-0.6"
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
url="http://www.pobox.com/users/dclark/mirror/pyOpenSSL-0.6.tar.gz
     http://umn.dl.sourceforge.net/sourceforge/pyopenssl/pyOpenSSL-0.6.tar.gz"
>

<configure>
/usr/local/lib/bcfg2/bin/python setup.py build_ext \
-I/usr/local/lib/bcfg2/include/openssl \
-L/usr/local/lib/bcfg2/lib/
</configure>

<build>
/usr/local/lib/bcfg2/bin/python setup.py build \
--build-base=${builddir}/build
</build>

<install>
/usr/local/lib/bcfg2/bin/python setup.py install \
--prefix=${ENCAP_SOURCE}/${ENCAP_PKGNAME}/lib/bcfg2
</install>

<clean>
/usr/local/lib/bcfg2/bin/python setup.py clean
</clean>

</source>

<prepackage type="set">
mkdir var 2>/dev/null || exit 0
mkdir var/encap 2>/dev/null || exit 0
touch var/encap/${ENCAP_PKGNAME}
</prepackage>

<encapinfo>
description pyOpenSSL - Python interface to the OpenSSL library
</encapinfo>

</encap_profile>
