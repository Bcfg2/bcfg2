# $Id$

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

DISTRO := $(shell cat /etc/issue | head -1)

ifeq ($(DISTRO),Debian GNU/Linux 3.1 \n \l)
PYTHON-APT = bcfg2-python-apt-0.5.10
endif

ifeq ($(DISTRO),Debian GNU/Linux testing/unstable \n \l)
PYTHON-APT = bcfg2-python-apt-0.6.19
endif

ifeq ($(DISTRO),Ubuntu 6.06.1 LTS \n \l)
PYTHON-APT = bcfg2-python-apt-0.6.16.2ubuntu8
endif

.ep.installed : # Clean, compile and install an encap package
	@printf "***** START .ep.installed for |$*| ***** \n"
	( apt-get install libapt-pkg-dev || true )
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

install : ${EPKG} ${MKENCAP} ${PYTHON-APT}.installed

encaps : ${EPKG} ${MKENCAP} ${PYTHON-APT}.packaged

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
	( ${EPKG} -q -r ${ENCAPDIR}/bcfg2-python-apt* || true )
	( rm -rf ${ENCAPDIR}/bcfg2-python-apt* || true )
