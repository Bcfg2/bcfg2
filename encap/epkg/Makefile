# $Id$

.PHONY : log all clean distclean install pkgconfig zlib openssl libtar curl fget expat epkg
.SUFFIXES : 

BASEDIR = /usr/local
ENCAPDIR = ${BASEDIR}/encap
PREFIX = /tmp/epkg-static-libs
PATH = ${PREFIX}/bin:/usr/sfw/bin:/usr/ccs/bin:/usr/local/bin:/opt/csw/bin:/usr/sbin:/usr/bin:/bin
CC = gcc -static-libgcc
LDFLAGS = -L${PREFIX}/lib
CPPFLAGS = -I${PREFIX}/include
LD_LIBRARY_PATH = ${PREFIX}/lib
LIBPATH = ${PREFIX}/lib
PKG_CONFIG_PATH = ${PREFIX}/lib/pkgconfig
ENCAP_CONTACT = dclark@pobox.com
export PATH CC LDFLAGS CPPFLAGS LD_LIBRARY_PATH LIBPATH PKG_CONFIG_PATH ENCAP_CONTACT

PKGCONFIG = pkg-config-0.22
ZLIB = zlib-1.2.3
LIBTAR = libtar-1.2.12
OPENSSL = openssl-0.9.8e
CURL = curl-7.16.4
FGET = fget-1.3.3
EXPAT = expat-2.0.1
EPKG = epkg-2.3.9

# Get Platform for GNU/Linux distributions...
UNAME := $(shell uname)

ifeq ($(UNAME),Linux)
DISTRO := $(shell cat /etc/issue | grep ^[a-zA-Z] | head -1)
UNAMEM := $(shell uname -m)
endif

## Get OS for GNU/Linux distributions...
ifeq ($(DISTRO),Debian GNU/Linux 3.1 \n \l)
OS = linux_debian_sarge
endif

ifeq ($(DISTRO),Debian GNU/Linux 4.0 \n \l)
OS = linux_debian_etch
endif

ifeq ($(DISTRO),Debian GNU/Linux testing/unstable \n \l)
OS = linux_debian_sid
endif

ifeq ($(DISTRO),Ubuntu 6.06.1 LTS \n \l)
OS = linux_ubuntu_dapper
endif

ifeq ($(DISTRO),Red Hat Linux release 6.0 (Hedwig))
OS = linux_redhat_60
endif

ifeq ($(DISTRO),Red Hat Linux release 7.2 (Enigma))
OS = linux_redhat_72
endif

ifeq ($(DISTRO),Welcome to SuSE SLES 8 (powered by UnitedLinux 1.0) (i586))
OS = linux_suse_sles8
endif

ifeq ($(DISTRO),Welcome to SUSE Linux Enterprise Server 10 (i586) - Kernel \r (\l).)
OS = linux_suse_sles10
endif

ifeq ($(DISTRO),Welcome to SUSE Linux Enterprise Server 10 (i686) - Kernel \r (\l).)
OS = linux_suse_sles10
endif

ifeq ($(DISTRO),Welcome to SUSE Linux Enterprise Server 10 (x86_64) - Kernel \r (\l).)
OS = linux_suse_sles10
endif

ifeq ($(DISTRO),Red Hat Enterprise Linux AS release 4 (Nahant Update 5))
OS = linux_redhat_rhel4
endif

ifeq ($(DISTRO),Red Hat Enterprise Linux AS release 4 (Nahant Update 4))
OS = linux_redhat_rhel4
endif

## Get ARCH for GNU/Linux distributions...
ARCH = ix86
ifeq ($(UNAMEM),x86_64)
ARCH = x86_64
endif

## Finally, set PLATFORM for GNU/Linux distributions...
PLATFORM = 
ifeq ($(UNAME),Linux)
PLATFORM = -p ${ARCH}-${OS}
endif

log:
	( $(MAKE) epkg.done > ./make.log 2>&1 ) &
	tail -f make.log
	
all: epkg.done

.DELETE_ON_ERROR : # delete the target of a rule if it has changed and its
                   # commands exit with a nonzero exit status

clean:
	-rm *.done
	-rm -rf ${PREFIX}

distclean: clean
	for D in ${PKGCONFIG} ${ZLIB} ${LIBTAR} ${OPENSSL} ${CURL} ${FGET} ${EXPAT} ${EPKG}; do (cd $$D && printf "In $$D \n" && (make clean 2>/dev/null || true) && (make distclean 2>/dev/null || true)); done
	if [ -f ${CURL}/lib/ca-bundle.crt.orig ]; then mv ${CURL}/lib/ca-bundle.crt.orig ${CURL}/lib/ca-bundle.crt; fi
	cd ${OPENSSL} && if [ -f config.orig ]; then mv config.orig config; fi
	-rm /usr/local/etc/epkg-ca-bundle.pem
	-rm /usr/local/etc/mkencap_environment
	-rm epkg-*-encap-*-*.tar.gz

pkgconfig.done:
	cd ${PKGCONFIG} && ./configure --prefix=${PREFIX} && $(MAKE) && $(MAKE) install
	touch pkgconfig.done

zlib.done: pkgconfig.done
	cd ${ZLIB} && prefix=${PREFIX} CC=gcc ./configure && $(MAKE) && $(MAKE) install
	touch zlib.done
	
openssl.done: zlib.done
	cd ${OPENSSL} && if [ -f config.orig ]; then cp config.orig config; fi
	cd ${OPENSSL} && cat config | sed s:CC\=ccc:CC\=gcc:g | sed s:CC\=cc:CC\=gcc:g > config.bcfg2
	cd ${OPENSSL} && mv config config.orig
	cd ${OPENSSL} && cp config.bcfg2 config
	cd ${OPENSSL} && chmod 755 config
	cd ${OPENSSL} && LDFLAGS="-all-static $LDFLAGS" ./config --prefix="${PREFIX}" zlib no-shared no-asm -L${PREFIX}/lib -I${PREFIX}/include && $(MAKE) && $(MAKE) install
	touch openssl.done

libtar.done: openssl.done
	cd ${LIBTAR} && ./configure --disable-encap --disable-epkg-install --prefix=${PREFIX} && $(MAKE) && $(MAKE) install
	touch libtar.done

curl.done: libtar.done
	if [ -f ${CURL}/lib/ca-bundle.crt ]; then mv ${CURL}/lib/ca-bundle.crt ${CURL}/lib/ca-bundle.crt.orig; fi
	cp cacert.pem ${CURL}/lib/ca-bundle.crt
	cd ${CURL} && ./configure --with-ssl --disable-ipv6 --disable-shared --enable-static --prefix=${PREFIX} --sysconfdir=/usr/local/etc --with-ca-bundle=/usr/local/etc/epkg-ca-bundle.pem && $(MAKE) && $(MAKE) install
	if [ -f ${CURL}/lib/ca-bundle.crt.orig ]; then mv ${CURL}/lib/ca-bundle.crt.orig ${CURL}/lib/ca-bundle.crt; fi
	${PREFIX}/bin/curl -V | xargs echo | grep zlib | grep ftp | grep http | grep libz | grep ftps | grep https
	touch curl.done

fget.done: curl.done
	cd ${FGET} && ./configure --disable-encap --disable-epkg-install --prefix=${PREFIX} && $(MAKE) && $(MAKE) install
	touch fget.done

expat.done: fget.done
	cd ${EXPAT} && ./configure --disable-shared --prefix=${PREFIX} && $(MAKE) && $(MAKE) install
	touch expat.done

epkg.done: expat.done
	test -d $(ENCAPDIR)/$(EPKG) && rm -rf $(ENCAPDIR)/$(EPKG) || true
	-rm /usr/local/etc/epkg-ca-bundle.pem
	-rm /usr/local/etc/mkencap_environment
	-rm epkg-*-encap-*-*.tar.gz
	cd ${EPKG} && ./configure && $(MAKE) && (rm -rf /usr/local/encap/epkg-2* 2>/dev/null || true) && $(MAKE) install
	cp cacert.pem /usr/local/encap/${EPKG}/epkg-ca-bundle.pem
	printf 'if [ ! -f "$${ENCAP_TARGET}/etc/epkg-ca-bundle.pem" ]; then\n\techo "installing: $${ENCAP_TARGET}/etc/epkg-ca-bundle.pem";\n\tcp "$${ENCAP_SOURCE}/$${ENCAP_PKGNAME}/epkg-ca-bundle.pem" "$${ENCAP_TARGET}/etc/epkg-ca-bundle.pem";\nfi\n' >> $(ENCAPDIR)/$(EPKG)/postinstall
	$(ENCAPDIR)/$(EPKG)/bin/mkencap $(PLATFORM) -ef $(EPKG)
	$(ENCAPDIR)/$(EPKG)/bin/mkencap $(PLATFORM) -c $(EPKG)
	$(ENCAPDIR)/$(EPKG)/bin/epkg -f -r epkg
	-rm /usr/local/etc/epkg-ca-bundle.pem
	-rm /usr/local/etc/mkencap_environment
	$(ENCAPDIR)/$(EPKG)/bin/epkg -f -i epkg
	$(ENCAPDIR)/$(EPKG)/bin/epkg -c
	test -f /usr/local/etc/epkg-ca-bundle.pem
	test -f /usr/local/etc/mkencap_environment
	touch epkg.done
