# $Id$

.PHONY : all clean distclean install zlib libtar curl fget expat epkg
.SUFFIXES : 

BASEDIR = /usr/local
ENCAPDIR = ${BASEDIR}/encap
PREFIX = /tmp/epkg-static-libs
PATH = ${PREFIX}/bin:/usr/sfw/bin:/usr/ccs/bin:/usr/local/bin:/opt/csw/bin:/usr/sbin:/usr/bin:/bin
CC = gcc -static-libgcc
LDFLAGS = -L${PREFIX}/lib
CPPFLAGS = -I${PREFIX}/include
export PATH LDFLAGS CPPFLAGS

ZLIB = zlib-1.2.3
LIBTAR = libtar-1.2.12
CURL = curl-7.16.4
FGET = fget-1.3.3
EXPAT = expat-2.0.1
EPKG = epkg-2.3.9

all: zlib libtar curl fget expat epkg

zlib:
	cd ${ZLIB} && prefix=${PREFIX} CC=gcc ./configure && $(MAKE) && $(MAKE) install

libtar:
	cd ${LIBTAR} && ./configure --disable-encap --disable-epkg-install --prefix=${PREFIX} && $(MAKE) && $(MAKE) install

curl:
	cd ${CURL} && ./configure --disable-ipv6 --disable-shared --prefix=${PREFIX} && $(MAKE) && $(MAKE) install

fget:
	cd ${FGET} && ./configure --disable-encap --disable-epkg-install --prefix=${PREFIX} && $(MAKE) && $(MAKE) install

expat:
	cd ${EXPAT} && ./configure --disable-shared --prefix=${PREFIX} && $(MAKE) && $(MAKE) install

epkg:
	test -d $(ENCAPDIR)/$(EPKG) && rm -rf $(ENCAPDIR)/$(EPKG) || true
	cd ${EPKG} && ./configure && $(MAKE) && $(MAKE) install
