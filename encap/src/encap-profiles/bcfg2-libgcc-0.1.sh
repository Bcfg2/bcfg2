#!/bin/sh
# $Id$

# Creates encap of libgcc libraries from build machine so other machines 
# don't need to have gcc installed, or in the case of GNU/Linux so we're 
# using a consistant libgcc version everywhere.

ENCAP_SOURCE=${ENCAPDIR}
ENCAP_PKGNAME=bcfg2-libgcc-0.1
PATH=$PATH:/usr/local/bin
export PATH

if [ "${ENCAP_SOURCE}x" = "x" ]; then 
	printf "Error in ${ENCAP_PKGNAME}.sh : ENCAPDIR not set, exiting...\n"
	exit 1
fi

umask 022

CXXBASE=`which gcc | xargs dirname | xargs dirname`
for LIB in `cd ${CXXBASE} && find lib | grep libgcc`; do
        cd ${CXXBASE}
        LIBDIR=`dirname ${LIB}`
        NEWDIR=${ENCAP_SOURCE}/${ENCAP_PKGNAME}/lib/bcfg2/${LIBDIR}
        if [ ! -d ${NEWDIR} ]; then mkdir -p ${NEWDIR}; fi
        cp -p ${LIB} ${NEWDIR}
done

SDIR=${ENCAP_SOURCE}/${ENCAP_PKGNAME}/var/encap
mkdir -p ${SDIR}
touch ${SDIR}/${ENCAP_PKGNAME}

exit 0

