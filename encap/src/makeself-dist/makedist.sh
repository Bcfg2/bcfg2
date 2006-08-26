#!/bin/sh -e

# $Id$

# Script to create the 
# bcfg2-<sitename>-<ver>-<arch>-<os>.run
# (example: bcfg2-nasa-1-rs6000-aix5.3.0.run)
# one-step install bcfg2 client distribution file

umask 002

# Set Variables
BASEDIR="/usr/local"
ENCAPDIR="${BASEDIR}/encap"
EPKG="${BASEDIR}/bin/epkg"
MAKESELF="/usr/local/bin/makeself.sh"
MDDIR="`pwd`"
BSDIR="$MDDIR/../bcfg2-site"
EPDIR="$MDDIR/../encap-profiles"

# Detect Variables
BSEP="`basename $BSDIR/bcfg2-site-*-encap-share.tar.gz`"
SITENAME="`echo $BSEP | awk -F\- '{print $3}'`"
SITEVER="`echo $BSEP | awk -F\- '{print $4}'`"

EPEP="`basename $EPDIR/m4-*-encap-*.tar.gz`"
ARCH="`echo $EPEP | awk -F\- '{print $4}'`"
OS="`echo $EPEP | awk -F\- '{print $5}' | awk -F. '{print $1}'`"

# Make temporary directory $DISTDIR from which distribution will be created
cd $MDDIR
DISTDIR="bcfg2-${SITENAME}-${SITEVER}-${ARCH}-${OS}"
if [ -d "$DISTDIR" ]; then rm -rf $DISTDIR; fi
mkdir $DISTDIR

# Copy epkg distribution to $DISTDIR
VERS="2.3.8 2.3.9"
for VER in $VERS; do
    if [ -d "$ENCAPDIR/epkg-${VER}" ]; then
        EPKGDIR="$ENCAPDIR/epkg-${VER}"
    fi
done
if [ "${EPKGDIR}x" = "x" ]; then
    printf "ERROR: Can't find your epkg directory to copy, exiting...\n"
    exit 1
fi
tar -cf $DISTDIR/epkg.tar $EPKGDIR/*

# Copy bcfg2 and client deps to $DISTDIR
BCFG2="`basename $EPDIR/bcfg2-[0-9].[0-9]*-encap-*.tar.gz`"
BCFG2_GETTEXT="`basename $EPDIR/bcfg2-gettext-*-encap-*.tar.gz`"
BCFG2_LIBGCC="`basename $EPDIR/bcfg2-libgcc-*.tar.gz`"
BCFG2_LIBICONV="`basename $EPDIR/bcfg2-libiconv-*-encap-*.tar.gz`"
BCFG2_LIBSTDCXX="`basename $EPDIR/bcfg2-libstdc++-*.tar.gz`"
BCFG2_LIBXML2="`basename $EPDIR/bcfg2-libxml2-*-encap-*.tar.gz`"
BCFG2_LIBXSLT="`basename $EPDIR/bcfg2-libxslt-*-encap-*.tar.gz`"
BCFG2_LXML="`basename $EPDIR/bcfg2-lxml-*-encap-*.tar.gz`"
BCFG2_OPENSSL="`basename $EPDIR/bcfg2-openssl-*-encap-*.tar.gz`"
BCFG2_PYOPENSSL="`basename $EPDIR/bcfg2-pyopenssl-*-encap-*.tar.gz`"
BCFG2_PYTHON="`basename $EPDIR/bcfg2-python-[0-9].[0-9]*-encap-*.tar.gz`"
BCFG2_ZLIB="`basename $EPDIR/bcfg2-zlib-*-encap-*.tar.gz`"
DAEMONTOOLS="`basename $EPDIR/daemontools-[0-9].[0-9]*-encap-*.tar.gz`"
OSTIARTY="`basename $EPDIR/ostiary-[0-9].[0-9]*-encap-*.tar.gz`"

BCFG2_PYTHON_APT_TMP="`basename $EPDIR/bcfg2-python-apt-*-encap-*.tar.gz`"
if [ "${BCFG2_PYTHON_APT_TMP}x" != 'bcfg2-python-apt-*-encap-*.tar.gzx' ]; then
    BCFG2_PYTHON_APT="$BCFG2_PYTHON_APT_TMP"
fi

BCFG2DEPS="$BCFG2_GETTEXT $BCFG2_LIBGCC $BCFG2_LIBICONV $BCFG2_LIBSTDCXX $BCFG2_LIBXML2 $BCFG2_LIBXSLT $BCFG2_LXML $BCFG2_OPENSSL $BCFG2_PYOPENSSL $BCFG2_PYTHON $BCFG2_ZLIB $BCFG2_PYTHON_APT"

FILES="$BCFG2DEPS $BCFG2 $DAEMONTOOLS $OSTIARTY"

for FILE in ${FILES}; do
    cp $EPDIR/$FILE $DISTDIR
done

# Copy bcfg2-site to $DISTDIR
BCFG2_SITE="$BSEP"
cp $BSDIR/$BCFG2_SITE $DISTDIR

# Create setup.sh in $DISTDIR
######################################################################
cat > $DISTDIR/setup.sh << EOF
#!/bin/sh

# \$Id$

# This is the script that is run by makeself after it extracts all the files
# from the .run distribution. It installs epkg, and then all the encaps in the
# right order (for client-side only, server side encaps just install manually)

umask 002

# Local Variables
LOC_INSTALLDIR="\`pwd\`"

# Install epkg if it isn't installed
if [ ! -h "$EPKG" ]; then
    set -x
    (cd / && tar xf \$LOC_INSTALLDIR/epkg.tar)
    $EPKGDIR/bin/epkg -i -q $EPKGDIR
    set +x
fi

# Install everything else
for LOC_BCFG2DEP in $BCFG2DEPS $DAEMONTOOLS $OSTIARTY $BCFG2; do
    LOC_PKGSPEC="\`printf "%s\n" "\$LOC_BCFG2DEP" | sed s:-encap.*::g\`"
    if [ -d "$ENCAPDIR/\$LOC_PKGSPEC" ]; then
        if [ "\${LOC_PKGSPEC}x" != "x" ]; then
            printf "\$LOC_BCFG2DEP : removing $ENCAPDIR/\$LOC_PKGSPEC\n"
            rm -rf $ENCAPDIR/\$LOC_PKGSPEC
        fi
    fi
    set -x
    $EPKG -i -q \$LOC_BCFG2DEP
    set +x
done

# Handle passwords if not already set...
# TODO

exit 0

EOF
######################################################################
chmod 755 $DISTDIR/setup.sh

# Create .run file from $DISTDIR with makeself
BLURB="Bcfg2 Client install for $SITENAME (version $SITEVER)"
${MAKESELF} --nox11 $DISTDIR ${DISTDIR}.run "$BLURB" ./setup.sh
