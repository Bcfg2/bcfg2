# $Id$

.PHONY : all clean distclean install zlib openssl libtar curl fget expat epkg
.SUFFIXES : 

BASEDIR = /usr/local
ENCAPDIR = ${BASEDIR}/encap
PREFIX = /tmp/epkg-static-libs
PATH = ${PREFIX}/bin:/usr/sfw/bin:/usr/ccs/bin:/usr/local/bin:/opt/csw/bin:/usr/sbin:/usr/bin:/bin
CC = gcc -static-libgcc
LDFLAGS = -all-static -L${PREFIX}/lib
CPPFLAGS = -I${PREFIX}/include
LD_LIBRARY_PATH = ${PREFIX}/lib
LIBPATH = ${PREFIX}/lib
export PATH CC LDFLAGS CPPFLAGS LD_LIBRARY_PATH LIBPATH

ZLIB = zlib-1.2.3
LIBTAR = libtar-1.2.12
OPENSSL = openssl-0.9.8e
CURL = curl-7.16.4
FGET = fget-1.3.3
EXPAT = expat-2.0.1
EPKG = epkg-2.3.9

all: epkg.done

zlib.done:
	cd ${ZLIB} && prefix=${PREFIX} CC=gcc ./configure && $(MAKE) && $(MAKE) install
	touch zlib.done
	
openssl.done: zlib.done
	cd ${OPENSSL} && if [ -f config.orig ]; then cp config.orig config; fi
	cd ${OPENSSL} && cat config | sed s:CC\=ccc:CC\=gcc:g | sed s:CC\=cc:CC\=gcc:g > config.bcfg2
	cd ${OPENSSL} && mv config config.orig
	cd ${OPENSSL} && cp config.bcfg2 config
	cd ${OPENSSL} && chmod 755 config
	cd ${OPENSSL} && ./config --prefix="${PREFIX}" zlib no-shared no-asm -L${PREFIX}/lib -I${PREFIX}/include && $(MAKE) && $(MAKE) install
	touch openssl.done

libtar.done: openssl.done
	cd ${LIBTAR} && ./configure --disable-encap --disable-epkg-install --prefix=${PREFIX} && $(MAKE) && $(MAKE) install
	touch libtar.done

curl.done: libtar.done
	cd ${CURL} && ./configure --disable-ipv6 --disable-shared --enable-static --prefix=${PREFIX} --with-ssl=${PREFIX} && $(MAKE) && $(MAKE) install
	touch curl.done

fget.done: curl.done
	cd ${FGET} && ./configure --disable-encap --disable-epkg-install --prefix=${PREFIX} && $(MAKE) && $(MAKE) install
	touch fget.done

expat.done: fget.done
	cd ${EXPAT} && ./configure --disable-shared --prefix=${PREFIX} && $(MAKE) && $(MAKE) install
	touch expat.done

epkg.done: expat.done
	test -d $(ENCAPDIR)/$(EPKG) && rm -rf $(ENCAPDIR)/$(EPKG) || true
	cd ${EPKG} && ./configure && $(MAKE) && $(MAKE) install
	touch epkg.done
