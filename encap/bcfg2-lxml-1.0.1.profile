<?xml version="1.0"?>

<!-- $Id$ -->

<encap_profile
	profile_ver="1.0"
	pkgspec="bcfg2-lxml-1.0.1"
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
        value="-L/usr/local/lib/bcfg2/lib -lexslt -L/usr/local/lib/bcfg2/lib/python2.4/site-packages -Wl,-rpath,/usr/local/lib/bcfg2/lib -Wl,-rpath,/usr/local/lib/bcfg2/lib/python2.4/site-packages"
PLATFORM_ELSE_IF_MATCH(aix)
        value="-L/usr/local/lib/bcfg2/lib -lexslt -L/usr/local/lib/bcfg2/lib/python2.4/site-packages -Wl,-blibpath:/usr/local/lib/bcfg2/lib:/usr/local/lib/bcfg2/lib/python2.4/site-packages:/usr/lib"
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
url="http://codespeak.net/lxml/lxml-1.0.1.tgz"
>

<configure>
/usr/local/lib/bcfg2/bin/python setup.py build_ext \
-I/usr/local/lib/bcfg2/include \
-L/usr/local/lib/bcfg2/lib \
-lexslt \
-L/usr/local/lib/bcfg2/lib/python2.4/site-packages
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
make clean
</clean>

</source>

<prepackage type="set">
mkdir var 2>/dev/null || exit 0
mkdir var/encap 2>/dev/null || exit 0
touch var/encap/${ENCAP_PKGNAME}
</prepackage>

<encapinfo>
description lxml - A Pythonic binding for the libxml2 and libxslt libraries
</encapinfo>

</encap_profile>
