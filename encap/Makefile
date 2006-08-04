# $Id$

.PHONY : all install clean uninstall encaps rename bcfg2only
.SUFFIXES : 
.SUFFIXES : .ep .sh .installed .packaged

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

.ep.installed : # Clean, compile and install an encap package
	@printf "***** START .ep.installed for |$*| ***** \n"
	( ${EPKG} -q -r ${ENCAPDIR}/$* || true )
	( rm -rf ${ENCAPDIR}/$* || true )
	( ${MKENCAP} -m /usr/local/bin/m4 -b -DUP $*.ep || true ) > $*.log 2>&1
	( ${MKENCAP} -m /usr/local/bin/m4 -b -T $*.ep || true ) >> $*.log 2>&1
	( ${MKENCAP} -m /usr/local/bin/m4 -b -CBI $*.ep ) >> $*.log 2>&1
	${EPKG} -q -i ${ENCAPDIR}/$*
	test -h ${BASEDIR}/var/encap/$*
	touch $*.installed
	@printf "***** STOP .ep.installed for |$*| ***** \n"

.sh.installed : # Create and install a "fake" encap package
	@printf "***** START .sh.installed for |$*| ***** \n"
	( ${EPKG} -q -r ${ENCAPDIR}/$* || true )
	( rm -rf ${ENCAPDIR}/$* || true )
	chmod 755 ./$*.sh
	./$*.sh
	${EPKG} -q -i ${ENCAPDIR}/$*
	test -h ${BASEDIR}/var/encap/$*
	touch $*.installed
	@printf "***** STOP .sh.installed for |$*| ***** \n"

.installed.packaged : # Create .tar.gz encap packages for distribution
	@printf "***** START .installed.packaged for |$*| ***** \n"
	( rm ${ENCAPDIR}/$*-*.tar.gz || true )
	( cd ${ENCAPDIR} && ${MKENCAP} -e $* || true )
	cd ${ENCAPDIR} && ${MKENCAP} -c $*
	mv ${ENCAPDIR}/$*-encap-*.tar.gz .
	touch $*.packaged
	@printf "***** STOP .installed.packaged for |$*| ***** \n"

all :
	( $(MAKE) install > make.log 2>&1 && $(MAKE) encaps >> make.log 2>&1 ) &

install : ${EPKG} ${MKENCAP} ${BCFG2}.installed

encaps : ${EPKG} ${MKENCAP} ${BCFG2}.packaged

rename : encaps
	test "$${OS}x" != "x"
	for EARCHIVE in `ls *-encap-*.tar.gz`; do \
		mv $${EARCHIVE} `printf $${EARCHIVE} | awk -F- '{$$NF = "OSDIST.tar.gz" ; print}' | sed s:\ :-:g | sed s:OSDIST:\$${OS}:g` ; \
	done

clean : 
	( rm *.log || true )
	( rm *.packaged || true )
	( rm *.gz || true )

uninstall : clean
	( rm *.installed || true )
	( ${EPKG} -q -r ${ENCAPDIR}/bcfg2-* || true )
	( rm -rf ${ENCAPDIR}/bcfg2-* || true )
	( rm -rf ${BASEDIR}/lib/bcfg2 || true )

bcfg2only :
	$(MAKE) -t; sleep 2; touch $(BCFG2).ep; $(MAKE)

${ZLIB}.installed : ${M4}.installed
${LIBICONV}.installed : ${ZLIB}.installed
${GETTEXT}.installed : ${LIBICONV}.installed
${PKG-CONFIG}.installed : ${GETTEXT}.installed
${OPENSSL}.installed : ${PKG-CONFIG}.installed
${LIBSTDCXX}.installed : ${OPENSSL}.installed
${LIBGCC}.installed : ${LIBSTDCXX}.installed
${PYTHON}.installed : ${LIBGCC}.installed
${PYREX}.installed : ${PYTHON}.installed
${PYOPENSSL}.installed : ${PYREX}.installed
${LIBXML2}.installed : ${PYOPENSSL}.installed	
${LIBXSLT}.installed : ${LIBXML2}.installed
${LXML}.installed : ${LIBXSLT}.installed
${BCFG2}.installed : ${LXML}.installed

${LIBICONV}.packaged : ${ZLIB}.packaged
${GETTEXT}.packaged : ${LIBICONV}.packaged
${OPENSSL}.packaged : ${GETTEXT}.packaged
${LIBSTDCXX}.packaged : ${OPENSSL}.packaged
${LIBGCC}.packaged : ${LIBSTDCXX}.packaged
${PYTHON}.packaged : ${LIBGCC}.packaged
${PYOPENSSL}.packaged : ${PYTHON}.packaged
${LIBXML2}.packaged : ${PYOPENSSL}.packaged
${LIBXSLT}.packaged : ${LIBXML2}.packaged
${LXML}.packaged : ${LIBXSLT}.packaged
${BCFG2}.packaged : ${LXML}.packaged
