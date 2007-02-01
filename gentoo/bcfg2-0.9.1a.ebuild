# Copyright 1999-2004 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: $

DESCRIPTION="Bcfg2 is a configuration management tool.  Package includes client
and server."
HOMEPAGE="http://www.mcs.anl.gov/cobalt/bcfg2"

# handle the "pre" case
MY_P="${P/_/}"
SRC_URI="ftp://ftp.mcs.anl.gov/pub/bcfg/${MY_P}.tar.gz"
S="${WORKDIR}/${MY_P}"

LICENSE="BSD"

SLOT="0"
KEYWORDS="~x86"
IUSE=""

DEPEND="app-portage/gentoolkit
    dev-python/elementtree
	dev-python/pyopenssl
	dev-python/lxml
	( || ( app-admin/gamin
	app-admin/fam ) )"

RDEPEND=""

src_compile() {
	python setup.py build
}

src_install() {
	install -d ${D}/usr/sbin
	install -d ${D}/etc/init.d
	exeinto /etc/init.d
	exeopts -m0755
	newexe ${FILESDIR}/bcfg2-server.rc bcfg2-server
	python setup.py install \
	   --root=${D} \
	   --record=PY_SERVER_LIBS \
	   --install-scripts /usr/sbin
}

pkg_postinst () {
	depscan.sh
}

pkg_postrm () {
	depscan.sh
}
