# $Id:$

.PHONY : all install clean uninstall encaps rename
.SUFFIXES : 
.SUFFIXES : .ep .installed .packaged

BASEDIR = /usr/local
ENCAPDIR = ${BASEDIR}/encap
export ENCAPDIR
EPKG = ${BASEDIR}/bin/epkg
export EPKG
MKENCAP = ${BASEDIR}/bin/mkencap
export MKENCAP

OSTIARTY = ostiary-3.4
OSTIARTY-DOC = ostiary-doc-20060801

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

install : ${EPKG} ${MKENCAP} ${OSTIARTY-DOC}.installed

encaps : ${EPKG} ${MKENCAP} ${OSTIARTY-DOC}.packaged

rename : encaps
	test "$${OS}x" != "x"
	for EARCHIVE in `ls *-encap-*.tar.gz`; do \
		mv $${EARCHIVE} `printf $${EARCHIVE} | awk -F- '{$$NF = "OSDIST.tar.gz" ; print}' | sed s:\ :-:g | sed s:OSDIST:\$${OS}:g` ; \
	done

clean : 
	( rm *.log || true )
	( rm *.packaged || true )
	( rm *.gz || true )
	( rm *~ || true )

uninstall : clean
	( rm *.installed || true )
	( ${EPKG} -q -r ${ENCAPDIR}/ostiary* || true )
	( rm -rf ${ENCAPDIR}/ostiary* || true )
    
${OSTIARTY-DOC}.installed : ${OSTIARTY}.installed

${OSTIARTY-DOC}.packaged : ${OSTIARTY}.packaged
