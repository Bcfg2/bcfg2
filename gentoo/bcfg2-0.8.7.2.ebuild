# Copyright 1999-2004 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: $

# NOTE: The comments in this file are for instruction and documentation.
# They're not meant to appear with your final, production ebuild.  Please
# remember to remove them before submitting or committing your ebuild.  That
# doesn't mean you can't add your own comments though.

# The 'Header' on the third line should just be left alone.  When your ebuild
# will be committed to cvs, the details on that line will be automatically
# generated to contain the correct data.

# Short one-line description of this package.
DESCRIPTION="Bcfg2 is a prototype configuration management tool"

# Homepage, not used by Portage directly but handy for developer reference
HOMEPAGE="http://www.mcs.anl.gov/cobalt/bcfg2"

# Point to any required sources; these will be automatically downloaded by
# Portage.
SRC_URI="ftp://ftp.mcs.anl.gov/pub/bcfg/${P}.tar.gz"

# License of the package. This must match the name of file(s) in
# /usr/portage/licenses/. For complex license combination see the developer
# docs on gentoo.org for details.
LICENSE="BSD"

# The SLOT variable is used to tell Portage if it's OK to keep multiple
# versions of the same package installed at the same time. For example,
# if we have a libfoo-1.2.2 and libfoo-1.3.2 (which is not compatible
# with 1.2.2), it would be optimal to instruct Portage to not remove
# libfoo-1.2.2 if we decide to upgrade to libfoo-1.3.2. To do this,
# we specify SLOT="1.2" in libfoo-1.2.2 and SLOT="1.3" in libfoo-1.3.2.
# emerge clean understands SLOTs, and will keep the most recent version
# of each SLOT and remove everything else.
# Note that normal applications should use SLOT="0" if possible, since
# there should only be exactly one version installed at a time.
# DO NOT USE SLOT=""! This tells Portage to disable SLOTs for this package.
SLOT="0"

# Using KEYWORDS, we can record masking information *inside* an ebuild
# instead of relying on an external package.mask file. Right now, you
# should set the KEYWORDS variable for every ebuild so that it contains
# the names of all the architectures with which the ebuild works. We have
# 4 official architecture names right now: "~x86", "~ppc", "~sparc"
# and "~alpha".  The ~ in front of the architecture indicates that the
# package is new and should be considered unstable until testing proves its
# stability.  Once packages go stable the ~ prefix is removed.
# So, if you've confirmed that your ebuild works on x86 and ppc,
# you'd specify: KEYWORDS="~x86 ~ppc"
# For packages that are platform-independent (like Java, PHP or Perl
# applications) specify all keywords.
# For binary packages, use -* and then list the archs the bin package
# exists for.  If the package was for an x86 binary package, then
# KEYWORDS would be set like this: KEYWORDS="-* x86"
# DO NOT USE KEYWORDS="*". This is deprecated and only for backward
# compatibility reasons.
KEYWORDS="~x86"

# Comprehensive list of any and all USE flags leveraged in the ebuild,
# with the exception of any ARCH specific flags, i.e. "ppc", "sparc",
# "x86" and "alpha". This is a required variable. If the
# ebuild doesn't use any USE flags, set to "".
IUSE=""

# Build-time dependencies, such as
#    ssl? ( >=dev-libs/openssl-0.9.6b )
#    >=dev-lang/perl-5.6.1-r1
# It is advisable to use the >= syntax show above, to reflect what you
# had installed on your system when you tested the package.  Then
# other users hopefully won't be caught without the right version of
# a dependency.
DEPEND=">=sss-0.99_pre6
    elementtree
	fam"

# Run-time dependencies, same as DEPEND if RDEPEND isn't defined:
#RDEPEND=""

# Source directory; the dir where the sources can be found (automatically
# unpacked) inside ${WORKDIR}.  S will get a default setting of ${WORKDIR}/${P}
# if you omit this line.
S=${WORKDIR}/${P}

src_compile() {
	# Most open-source packages use GNU autoconf for configuration.
	# You should use something similar to the following lines to
	# configure your package before compilation.  The "|| die" portion
	# at the end will stop the build process if the command fails.
	# You should use this at the end of critical commands in the build
	# process.  (Hint: Most commands are critical, that is, the build
	# process should abort if they aren't successful.)
	python setup.py build
	# Note the use of --infodir and --mandir, above. This is to make
	# this package FHS 2.2-compliant.  For more information, see
	#   http://www.pathname.com/fhs/

	# Also note that it is cleaner and easier to use econf, which is the
	# portage shortcut to the above ./configure statement:
	#
	# econf || die
	# Note that econf will die on failure, but plase use econf || die
	# for consistency.

	# emake (previously known as pmake) is a script that calls the
	# standard GNU make with parallel building options for speedier
	# builds (especially on SMP systems).  Try emake first.  It might
	# not work for some packages, in which case you'll have to resort
	# to normal "make".
	#make || die
}

src_install() {
	# You must *personally verify* that this trick doesn't install
	# anything outside of DESTDIR; do this by reading and
	# understanding the install part of the Makefiles.
	#make DESTDIR=${D} install || die
	install -d ${D}/usr/sbin
	install -d ${D}/etc/init.d
	exeinto /etc/init.d
	exeopts -m0755
	doexe ${FILESDIR}/bcfg2-server ${FILESDIR}/bcfg2-client
	# dosbin bcfgd.py bcfgctl.py bcfg.py bcfg-refresh.py
	# doman bcfg.1 bcfgctl.1 bcfgd.8 bcfgd.conf.5
	# dodoc README LICENSE docs/*
	# docinto examples
	# dodoc test/*							
	python setup.py install --root=${D} --record=PY_SERVER_LIBS
	
	# For Makefiles that don't make proper use of DESTDIR, setting
	# prefix is often an alternative.  However if you do this, then
	# you also need to specify mandir and infodir, since they were
	# passed to ./configure as absolute paths (overriding the prefix
	# setting).
	#make \
	#	prefix=${D}/usr \
	#	mandir=${D}/usr/share/man \
	#	infodir=${D}/usr/share/info \
	#	install || die
	# Again, verify the Makefiles!  We don't want anything falling
	# outside of ${D}.Q
	# `												

	# The portage shortcut to the above command is simply:
	#
	#einstall || die
	# Note that einstall will die on failure, but please use einstall || die
	# for consistency.
}

pkg_postinst () {
	depscan.sh
}

pkg_postrm () {
	[ -f /etc/init.d/bcfg2-client ] && rm -f /etc/init.d/bcfg2-client
	[ -f /etc/init.d/bcfg2-server ] && rm -f /etc/init.d/bcfg2-server
	depscan.sh
}
