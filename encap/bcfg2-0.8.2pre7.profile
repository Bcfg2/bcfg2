<?xml version="1.0"?>

<!-- $Id$ -->

<encap_profile
	profile_ver="1.0"
	pkgspec="bcfg2-0.8.2pre7"
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
url="ftp://ftp.mcs.anl.gov/pub/bcfg/bcfg2-0.8.2pre7.tar.gz"
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
--prefix=${ENCAP_SOURCE}/${ENCAP_PKGNAME}/lib/bcfg2
</install>

<clean>
/usr/local/lib/bcfg2/bin/python setup.py clean
</clean>

</source>

<prepackage type="set"><![CDATA[
mkdir bin 2>/dev/null || exit 0
ln -sf ../lib/bcfg2/bin/GenerateHostInfo bin/
ln -sf ../lib/bcfg2/bin/StatReports bin/
ln -sf ../lib/bcfg2/bin/bcfg2 bin/
ln -sf ../lib/bcfg2/bin/bcfg2-info bin/
ln -sf ../lib/bcfg2/bin/bcfg2-repo-validate bin/
ln -sf ../lib/bcfg2/bin/bcfg2-server bin/
mkdir share 2>/dev/null || exit 0
mkdir share/bcfg2  2>/dev/null || exit 0
cp ${builddir}/doc/manual.pdf share/bcfg2/
cp -r ${builddir}/examples share/bcfg2/
mkdir var 2>/dev/null || exit 0
mkdir var/encap 2>/dev/null || exit 0
touch var/encap/${ENCAP_PKGNAME}
]]></prepackage>

<encapinfo>
description Bcfg2 - Provides a declarative interface to system configuration
prereq pkgspec >= bcfg2-zlib-1.2.3
prereq pkgspec >= bcfg2-libiconv-1.9.2
prereq pkgspec >= bcfg2-gettext-0.14.5
prereq pkgspec >= bcfg2-openssl-0.9.8b
prereq pkgspec >= bcfg2-libstdc++-0.1
prereq pkgspec >= bcfg2-libgcc-0.1
prereq pkgspec >= bcfg2-python-2.4.3
prereq pkgspec >= bcfg2-pyopenssl-0.6
prereq pkgspec >= bcfg2-libxml2-2.6.26
prereq pkgspec >= bcfg2-libxslt-1.1.17
prereq pkgspec >= bcfg2-lxml-1.0.1
</encapinfo>

</encap_profile>
