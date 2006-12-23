# Copyright 1999-2004 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: $

DESCRIPTION="Bcfg2 is a configuration management tool.  Package includes client
and server."
HOMEPAGE="http://www.mcs.anl.gov/cobalt/bcfg2"

# MY_PV=`echo $PV | sed -e 's/_//g'`
# SRC_URI="ftp://ftp.mcs.anl.gov/pub/bcfg/${PN}-${MY_PV}.tar.gz"
SRC_URI="ftp://ftp.mcs.anl.gov/pub/bcfg/${P}.tar.gz"
LICENSE="BSD"

SLOT="0"
KEYWORDS="~x86"
IUSE=""

# mrj added gamin as an alternative to fam, since that's what i'm using.
DEPEND="dev-python/elementtree
	( || ( app-admin/gamin
	app-admin/fam ) )"

RDEPEND=""

S=${WORKDIR}/${P}

src_compile() {
	python setup.py build
}

src_install() {
	install -d ${D}/usr/sbin
	install -d ${D}/etc/init.d
	exeinto /etc/init.d
	exeopts -m0755
	doexe ${FILESDIR}/bcfg2-server ${FILESDIR}/bcfg2-client
	python setup.py install --root=${D} --record=PY_SERVER_LIBS
}

pkg_postinst () {
	depscan.sh
}

pkg_postrm () {
	[ -f /etc/init.d/bcfg2-client ] && rm -f /etc/init.d/bcfg2-client
	[ -f /etc/init.d/bcfg2-server ] && rm -f /etc/init.d/bcfg2-server
	depscan.sh
}
