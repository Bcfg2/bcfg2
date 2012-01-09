# Copyright 1999-2011 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Header: $

EAPI="3"
PYTHON_DEPEND="2:2.6"
SUPPORT_PYTHON_ABIS="1"
# ssl module required.
RESTRICT_PYTHON_ABIS="2.4 2.5 3.*"

inherit distutils

DESCRIPTION="configuration management tool"
HOMEPAGE="http://bcfg2.org"

# handle the "pre" case
MY_P="${P/_/}"
SRC_URI="ftp://ftp.mcs.anl.gov/pub/bcfg/${MY_P}.tar.gz"
S="${WORKDIR}/${MY_P}"

LICENSE="BSD"
SLOT="0"
KEYWORDS="~amd64 ~x86 ~amd64-linux ~x86-linux ~x64-solaris"
IUSE="server"

DEPEND=""
RDEPEND="app-portage/gentoolkit
	server? (
		dev-python/lxml
		dev-libs/libgamin[python] )"

PYTHON_MODNAME="Bcfg2"

distutils_src_install_post_hook() {
	if ! use server; then
		rm -f "$(distutils_get_intermediate_installation_image)${EPREFIX}/usr/sbin/bcfg2-"*
	fi
}

src_install() {
	distutils_src_install --record=PY_SERVER_LIBS --install-scripts "${EPREFIX}/usr/sbin"

	if ! use server; then
	    # Remove files only necessary for a server installation
		rm -rf "${ED}usr/share/bcfg2"
		rm -rf "${ED}usr/share/man/man8"
	else
		newinitd "${FILESDIR}/bcfg2-server.rc" bcfg2-server
	fi

	insinto /etc
	doins examples/bcfg2.conf || die "doins failed"
}

pkg_postinst () {
	distutils_pkg_postinst

	if use server; then
		einfo "If this is a new installation, you probably need to run:"
		einfo "    bcfg2-admin init"
	fi
}
