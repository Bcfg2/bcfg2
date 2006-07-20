# $Id$

.PHONY : all install clean uninstall encaps rename
.SUFFIXES : 
.SUFFIXES : .profile .sh .e .ep

BASEDIR = /usr/local
ENCAPDIR = ${BASEDIR}/encap
export ENCAPDIR
EPKG = ${BASEDIR}/bin/epkg
export EPKG
MKENCAP = ${BASEDIR}/bin/mkencap
export MKENCAP

M4 = m4-1.4.4
ZLIB = bcfg2-zlib-1.2.3
LIBICONV = bcfg2-libiconv-1.9.2
GETTEXT = bcfg2-gettext-0.14.5
PKG-CONFIG = bcfg2-pkg-config-0.20
PATCH = bcfg2-patch-2.5.9
OPENSSL = bcfg2-openssl-0.9.8b
LIBSTDCXX = bcfg2-libstdc++-0.1
LIBGCC = bcfg2-libgcc-0.1
PYTHON = bcfg2-python-2.4.3
PYREX = bcfg2-pyrex-0.9.4.1
PYOPENSSL = bcfg2-pyopenssl-0.6
LIBXML2 = bcfg2-libxml2-2.6.26
LIBXSLT = bcfg2-libxslt-1.1.17
LXML = bcfg2-lxml-1.0.1
BCFG2 = bcfg2-0.8.2

.profile.e : # Clean, compile and install an encap package
	@printf "***** START .profile.e for |$*| ***** \n"
	( ${EPKG} -q -r ${ENCAPDIR}/$* || true )
	( rm -rf ${ENCAPDIR}/$* || true )
	( ${MKENCAP} -m /usr/local/bin/m4 -b -DUP $*.profile || true ) > $*.log 2>&1
	( ${MKENCAP} -m /usr/local/bin/m4 -b -T $*.profile || true ) >> $*.log 2>&1
	( ${MKENCAP} -m /usr/local/bin/m4 -b -CBI $*.profile ) >> $*.log 2>&1
	${EPKG} -q -i ${ENCAPDIR}/$*
	test -h ${BASEDIR}/var/encap/$*
	touch $*.e
	@printf "***** STOP .profile.e for |$*| ***** \n"

.sh.e : # Create and install a "fake" encap package
	@printf "***** START .sh.e for |$*| ***** \n"
	( ${EPKG} -q -r ${ENCAPDIR}/$* || true )
	( rm -rf ${ENCAPDIR}/$* || true )
	./$*.sh
	${EPKG} -q -i ${ENCAPDIR}/$*
	test -h ${BASEDIR}/var/encap/$*
	touch $*.e
	@printf "***** STOP .sh.e for |$*| ***** \n"

.e.ep : # Create .tar.gz encap packages for distribution to other machines
	@printf "***** START .e.ep for |$*| ***** \n"
	( rm ${ENCAPDIR}/$*-*.tar.gz || true )
	( cd ${ENCAPDIR} && ${MKENCAP} -e $* || true )
	cd ${ENCAPDIR} && ${MKENCAP} -c $*
	mv ${ENCAPDIR}/$*-encap-*.tar.gz .
	touch $*.ep
	@printf "***** STOP .e.ep for |$*| ***** \n"

all :
	( $(MAKE) install > make.log 2>&1 && $(MAKE) encaps >> make.log 2>&1 ) &

install : ${EPKG} ${MKENCAP} ${BCFG2}.e

encaps : ${EPKG} ${MKENCAP} ${BCFG2}.ep

rename : encaps
	test "$${OS}x" != "x"
	for EARCHIVE in `ls *-encap-*.tar.gz`; do \
		mv $${EARCHIVE} `printf $${EARCHIVE} | awk -F- '{$$NF = "OSDIST.tar.gz" ; print}' | sed s:\ :-:g | sed s:OSDIST:\$${OS}:g` ; \
	done

clean : 
	( rm *.log || true )
	( rm *.ep || true )
	( rm *.gz || true )

uninstall : clean
	( rm *.e || true )
	( ${EPKG} -q -r ${ENCAPDIR}/bcfg2-* || true )
	( rm -rf ${ENCAPDIR}/bcfg2-* || true )
	( rm -rf ${BASEDIR}/lib/bcfg2 || true )

${ZLIB}.e : ${M4}.e
${LIBICONV}.e : ${ZLIB}.e
${GETTEXT}.e : ${LIBICONV}.e
${PKG-CONFIG}.e : ${GETTEXT}.e
${PATCH}.e : ${PKG-CONFIG}.e
${OPENSSL}.e : ${PATCH}.e
${LIBSTDCXX}.e : ${OPENSSL}.e
${LIBGCC}.e : ${LIBSTDCXX}.e
${PYTHON}.e : ${LIBGCC}.e
${PYREX}.e : ${PYTHON}.e
${PYOPENSSL}.e : ${PYREX}.e
${LIBXML2}.e : ${PYOPENSSL}.e	
${LIBXSLT}.e : ${LIBXML2}.e
${LXML}.e : ${LIBXSLT}.e
${BCFG2}.e : ${LXML}.e

${LIBICONV}.ep : ${ZLIB}.ep
${GETTEXT}.ep : ${LIBICONV}.ep
${PATCH}.ep : ${GETTEXT}.ep
${OPENSSL}.ep : ${PATCH}.ep
${LIBSTDCXX}.ep : ${OPENSSL}.ep
${LIBGCC}.ep : ${LIBSTDCXX}.ep
${PYTHON}.ep : ${LIBGCC}.ep
${PYOPENSSL}.ep : ${PYTHON}.ep
${LIBXML2}.ep : ${PYOPENSSL}.ep
${LIBXSLT}.ep : ${LIBXML2}.ep
${LXML}.ep : ${LIBXSLT}.ep
${BCFG2}.ep : ${LXML}.ep

