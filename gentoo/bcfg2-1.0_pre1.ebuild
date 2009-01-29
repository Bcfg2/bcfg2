# Copyright 1999-2004 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: $

DESCRIPTION="Bcfg2 is a configuration management tool.  Package includes client
and server."
HOMEPAGE="http://trac.mcs.anl.gov/projects/bcfg2"

# handle the "pre" case
MY_P="${P/_/}"
SRC_URI="ftp://ftp.mcs.anl.gov/pub/bcfg/${MY_P}.tar.gz"
S="${WORKDIR}/${MY_P}"

LICENSE="BSD"
RESTRICT="mirror"

SLOT="0"
KEYWORDS="~x86 ~amd64"
IUSE="server"

DEPEND="
	app-portage/gentoolkit

	|| ( >=dev-lang/python-2.5 
		( 	
			>=dev-lang/python-2.3 
			|| ( dev-python/elementtree dev-python/lxml )
		)
	)
	"

RDEPEND="
	server? (
		dev-python/pyopenssl
		|| ( app-admin/gamin app-admin/fam ) 
	)
	"

src_compile() {
	python setup.py build
}

src_install() {
	python setup.py install \
	   --root=${D} \
	   --record=PY_SERVER_LIBS \
	   --install-scripts /usr/sbin

	# Remove files only necessary for a server installation
	if ! use server; then
		rm -rf ${D}/usr/sbin/bcfg2-*
		rm -rf ${D}/usr/share/bcfg2
		rm -rf ${D}/usr/share/man/man8
	fi

	# Install a server init.d script
	if use server; then
		newinitd ${FILESDIR}/bcfg2-server.rc bcfg2-server
	fi

	insinto /etc
	doins ${S}/examples/bcfg2.conf
}

pkg_postinst () {
	depscan.sh
}

pkg_postrm () {
	depscan.sh
}
