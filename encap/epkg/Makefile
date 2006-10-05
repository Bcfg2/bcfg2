# $Id$

.PHONY : all clean distclean install zlib libtar openssl curl fget expat epkg
.SUFFIXES : 

BASEDIR = /usr/local
ENCAPDIR = ${BASEDIR}/encap
PREFIX = /tmp/epkg-static-libs
PATH = ${PREFIX}/bin:/usr/sfw/bin:/usr/ccs/bin:/usr/local/bin:/opt/csw/bin:/usr/sbin:/usr/bin:/bin
CC = gcc
LDFLAGS = -L${PREFIX}/lib
CPPFLAGS = -I${PREFIX}/include
export PATH LDFLAGS CPPFLAGS

ZLIB = zlib-1.2.3
LIBTAR = libtar-1.2.11
OPENSSL = openssl-0.9.8c
CURL = curl-7.15.4
FGET = fget-1.3.3
EXPAT = expat-2.0.0
EPKG = epkg-2.3.9

all: zlib libtar openssl curl fget expat epkg

zlib:
	cd ${ZLIB} && prefix=${PREFIX} CC=gcc ./configure && $(MAKE) && $(MAKE) install

libtar:
	cd ${LIBTAR} && ./configure --disable-encap --disable-epkg-install --prefix=${PREFIX} && $(MAKE) && $(MAKE) install

openssl:
	cd ${OPENSSL} && ./config --prefix=${PREFIX} zlib no-asm no-shared && $(MAKE) && $(MAKE) install 

curl:
	cd ${CURL} && ./configure --disable-ipv6 --disable-shared --prefix=${PREFIX} && $(MAKE) && $(MAKE) install

fget:
	cd ${FGET} && ./configure --disable-encap --disable-epkg-install --prefix=${PREFIX} && $(MAKE) && $(MAKE) install

expat:
	cd ${EXPAT} && ./configure --disable-shared --prefix=${PREFIX} && $(MAKE) && $(MAKE) install

epkg:
	cd ${EPKG} && ./configure && $(MAKE) && $(MAKE) install
