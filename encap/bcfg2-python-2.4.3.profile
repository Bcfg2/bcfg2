<?xml version="1.0"?>

<!-- $Id$ -->

<encap_profile
	profile_ver="1.0"
	pkgspec="bcfg2-python-2.4.3"
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
	url="http://www.pobox.com/users/dclark/mirror/Python-2.4.3.tgz
	     http://www.python.org/ftp/python/2.4.3/Python-2.4.3.tgz"
>

<configure>
./configure \
	--prefix="${ENCAP_SOURCE}/${ENCAP_PKGNAME}/lib/bcfg2" \
PLATFORM_IF_MATCH(aix)
	--with-gcc \
	--with-cxx=g++ \
PLATFORM_ENDIF
	--enable-shared=yes \
	--disable-ipv6
</configure>

</source>

<prepackage><![CDATA[
echo /usr/local/lib/bcfg2/lib/python2.4/site-packages > lib/bcfg2/lib/python2.4/site-packages/usr-local-lib-bcfg2.pth
mkdir bin 2>/dev/null || exit 0
ln -sf ../lib/bcfg2/bin/idle bin/b2idle
ln -sf ../lib/bcfg2/bin/pydoc bin/b2pydoc
ln -sf ../lib/bcfg2/bin/python bin/b2python
mkdir var 2>/dev/null || exit 0
mkdir var/encap 2>/dev/null || exit 0
touch var/encap/${ENCAP_PKGNAME}
]]></prepackage>

<encapinfo>
description Python - Scripting language
</encapinfo>

</encap_profile>
