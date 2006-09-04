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

# Make sure /usr/local/man exists
if [ ! -d /usr/local ]; then mkdir /usr/local; fi
if [ -h /usr/local/man ]; then rm /usr/local/man; fi
if [ ! -d /usr/local/man ]; then mkdir /usr/local/man; fi

# Install epkg if it isn't installed
if [ ! -h "$EPKG" -o ! -d "$ENCAPDIR/epkg-2.3.[89]" ]; then
    printf "epkg : (cd / && tar xf \$LOC_INSTALLDIR/epkg.tar)\n"
    (cd / && tar xf \$LOC_INSTALLDIR/epkg.tar)
    printf "epkg : $EPKGDIR/bin/epkg -i -q $EPKGDIR\n"
    $EPKGDIR/bin/epkg -i -q $EPKGDIR
fi

# Install everything else
for LOC_PKG in $BCFG2DEPS $BCFG2 $DAEMONTOOLS $OSTIARTY $BCFG2_SITE; do
    LOC_PKGSPEC="\`printf "%s\n" "\$LOC_PKG" | sed s:-encap.*::g\`"
    if [ -d "$ENCAPDIR/\$LOC_PKGSPEC" ]; then
        if [ "\${LOC_PKGSPEC}x" != "x" ]; then
            printf "\$LOC_PKGSPEC : removing $ENCAPDIR/\$LOC_PKGSPEC\n"
            ($EPKG -r -q $ENCAPDIR/\$LOC_PKGSPEC || true)
            rm -rf $ENCAPDIR/\$LOC_PKGSPEC
        fi
    fi
    printf "\$LOC_PKGSPEC : installing \${LOC_PKG}\n"
    $EPKG -i -q \$LOC_PKG
done

## Handle passwords if not already set... [
# Define variables
LOC_BCFG2_CONF="/usr/local/etc/bcfg2.conf"
LOC_BCFG2_RE='^password\ =\ $'
LOC_OST_CFG="/usr/local/etc/ostiary.cfg"
LOC_OST_KILL_RE='^KILL=\"-kill\"$'
LOC_OST_ACTION_RE='^ACTION=\"-bcfg2-'

# Check to see if passwords are set
printf "Checking to see if password is set in \'\${LOC_BCFG2_CONF}\'... "
grep "\${LOC_BCFG2_RE}" \$LOC_BCFG2_CONF >/dev/null && LOC_BCFG2_SET="no"
if [ "\${LOC_BCFG2_SET}x" = "nox" ]; then 
    printf "no\n"
else 
    printf "yes\n"
fi

printf "Checking to see if passwords are set in \'\${LOC_OST_CFG}\'... "
grep "\${LOC_OST_KILL_RE}" \$LOC_OST_CFG >/dev/null && LOC_OST_SET="no"
grep "\${LOC_OST_ACTION_RE}" \$LOC_OST_CFG >/dev/null && LOC_OST_SET="no"
if [ "\${LOC_OST_SET}x" = "nox" ]; then 
    printf "no\n"
else 
    printf "yes\n"
fi

# Password read function
getpasswd() {
    password1=""; password2=""; password=""
    stty -echo
    trap "stty echo ; echo 'Interrupted' ; exit 1" 1 2 3 15
    printf "Enter \$1 password: "
    read -r password1
    printf "\n"
    printf "Enter \$1 password again: "
    read -r password2
    printf "\n"
    stty echo
    if [ "\${password1}x" != "\${password2}x" ]; then
        printf "The passwords did not match, please try again...\n"
        getpasswd "\$1"
    else
        password="\${password1}"
    fi
}

# Securely prompt sysadmin for passwords that are not either already set or
# in the environment as LOC_BCFG2_PASSWD and/or LOC_OST_PASSWD
if [ "\${LOC_BCFG2_SET}x" = "nox" ]; then
    # You can set passwords as env variables to avoid interactive mode
    if [ "\${LOC_BCFG2_PASSWD}x" = "x" ]; then
        getpasswd bcfg2
        LOC_BCFG2_PASSWD="\$password"
    else
        printf "Got LOC_BCFG2_PASSWD from environment...\n"
    fi
fi

if [ "\${LOC_OST_SET}x" = "nox" ]; then
    # You can set passwords as env variables to avoid interactive mode
    if [ "\${LOC_OST_PASSWD}x" = "x" ]; then
        getpasswd "ostiary base"
        LOC_OST_PASSWD="\$password"
    else
        printf "Got LOC_OST_PASSWD from environment...\n"
    fi
fi

# Sed quoting function - quote the &, :, ' and \ characters
sedquote() {
    i=1 
    while [ \$i -le \`expr length \$1\` ]; do
        c=\`expr substr \$1 \$i 1\`
        if [ "\${c}x" = "&x" -o "\${c}x" = ":x" -o "\${c}x" = "'x" -o "\${c}x" = "\\\\x" ]; then
            c=\\\\\${c}
        fi
        printf "%s" "\$c"
        i=\`expr \$i + 1\`
    done
}

# Edit files with supplied password values
umask 077

if [ "\${LOC_BCFG2_SET}x" = "nox" ]; then
    printf "Setting bcfg2 password...\n"
    chmod 600 \$LOC_BCFG2_CONF
    LOC_BCFG2_SED="\$LOC_INSTALLDIR/loc_bcfg2.sed"
    printf "s:%s:password = %s:g\n" "\$LOC_BCFG2_RE" "\`sedquote "\${LOC_BCFG2_PASSWD}"\`" > \$LOC_BCFG2_SED
    sed -f \$LOC_BCFG2_SED \$LOC_BCFG2_CONF > \${LOC_BCFG2_CONF}.withpasswords
    chmod 600 \${LOC_BCFG2_CONF}.withpasswords
    mv \${LOC_BCFG2_CONF}.withpasswords \${LOC_BCFG2_CONF}
fi

if [ "\${LOC_OST_SET}x" = "nox" ]; then
    printf "Setting ostiary passwords...\n"
    chmod 600 \$LOC_OST_CFG
    LOC_OST_KILL_SED="\$LOC_INSTALLDIR/loc_ost_kill.sed"
    LOC_OST_ACTION_SED="\$LOC_INSTALLDIR/loc_ost_action.sed"
    printf "s:%s:KILL=%s-kill:g\n" "\$LOC_OST_KILL_RE" "\`sedquote "\${LOC_OST_PASSWD}"\`" > \$LOC_OST_KILL_SED
    printf "s:%s:ACTION=\\"%s-bcfg2-:g\n" "\$LOC_OST_ACTION_RE" "\`sedquote "\${LOC_OST_PASSWD}"\`" > \$LOC_OST_ACTION_SED
    sed -f \$LOC_OST_KILL_SED \$LOC_OST_CFG | sed -f \$LOC_OST_ACTION_SED \
    > \${LOC_OST_CFG}.withpasswords
    chmod 600 \${LOC_OST_CFG}.withpasswords
    mv \${LOC_OST_CFG}.withpasswords \${LOC_OST_CFG}
fi

## ]

# Just to be paranoid...
chown 0 \${LOC_BCFG2_CONF}*
chown 0 \${LOC_OST_CFG}*
chgrp 0 \${LOC_BCFG2_CONF}*
chgrp 0 \${LOC_OST_CFG}*
chmod 600 \${LOC_BCFG2_CONF}*
chmod 600 \${LOC_OST_CFG}*

# Restart services if they exist to catch any config file changes
if [ -x /command/svc -a -x /command/svstat ]; then
    for LOC_SERVICE in bcfg2-client bcfg2-server ostiary; do
        if [ -h /service/\${LOC_SERVICE} ]; then
            printf "Restarting daemontools service \${LOC_SERVICE}...\n" 
            /command/svc -t /service/\${LOC_SERVICE}
            sleep 2
            /command/svstat /service/\${LOC_SERVICE}
        fi
    done
fi
    
exit 0

EOF
######################################################################
chmod 755 $DISTDIR/setup.sh

# Create .run file from $DISTDIR with makeself
BLURB="Bcfg2 Client install for $SITENAME (version $SITEVER) - export REPLACE_CONFIG=yes before running to force config file replacement"
${MAKESELF} --nox11 $DISTDIR ${DISTDIR}.run "$BLURB" ./setup.sh

exit 0
