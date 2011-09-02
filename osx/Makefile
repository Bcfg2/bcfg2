PYVERSION := $(shell /usr/bin/python -c "import sys; print '%s.%s' % (sys.version_info[0], sys.version_info[1])")
PYMAJORVERSION := $(shell /usr/bin/python -c "import sys; print sys.version_info[0]")
PYMINORVERSION := $(shell /usr/bin/python -c "import sys; print sys.version_info[1]")
PREFLIGHT = preflight
POSTFLIGHT = postflight
PKGROOT = bcfg2pkg
PKGTMP = bcfg2tmp
FILTERS = --filter Hostbase \
--filter Reports \
--filter Server \
--filter xsd \
--filter xsl \
--filter bcfg2-admin \
--filter bcfg2-build-reports \
--filter bcfg2-info \
--filter bcfg2-ping-sweep \
--filter bcfg2-lint \
--filter bcfg2-reports \
--filter bcfg2-server

CONF = bcfg2.conf
DATADIR = /Library/Frameworks/Python.framework/Versions/Current
LAUNCHD = gov.anl.mcs.bcfg2-daily.plist
PACKAGEMAKER = /Developer/usr/bin/packagemaker
PROTO_PLIST = PackageInfo.plist
SITELIBDIR = /Library/Python/${PYVERSION}/site-packages

# Symlinks cannot be specified on the command line, therefore, we create
# an Info.plist file for packagemaker to look at for package creation
# and substitute the version strings. Major/Minor versions can only be
# integers (e.g. "1" and "00" for bcfg2 version 1.0.0.
BCFGVER = 1.2.0rc1
MAJOR = 1
MINOR = 20

default: clean client

install:
	echo "Installing Bcfg2 to ${PKGROOT}"
	mkdir -p ${PKGROOT}
	cd ../ && /usr/bin/python setup.py install \
	       --root="osx/${PKGROOT}" \
	       --install-lib="${SITELIBDIR}" \
	       --install-data="${DATADIR}"

prepare: install
	mkdir -p ${PKGTMP}
	cp ${PROTO_PLIST} ${PKGTMP}
	sed -i '' "s/{SHORTVERSION}/${BCFGVER}/g" "${PKGTMP}/${PROTO_PLIST}"
	sed -i '' "s/{MAJORVERSION}/${MAJOR}/g" "${PKGTMP}/${PROTO_PLIST}"
	sed -i '' "s/{MINORVERSION}/${MINOR}/g" "${PKGTMP}/${PROTO_PLIST}"

	# create a preflight script to remove traces of previous
	# bcfg2 installs due to limitations in Apple's pkg format
	mkdir -p "${PKGTMP}/scripts"
	cp "${PREFLIGHT}" "${PKGTMP}/scripts"
	cp "${POSTFLIGHT}" "${PKGTMP}/scripts"

	# substitute in the {sitelib,data}dir specified above on the assumption that
	# this is where any previous bcfg2 install exists that should be cleaned out.
	sed -i '' "s|{SITELIBDIR}|${SITELIBDIR}|g" "${PKGTMP}/scripts/${PREFLIGHT}"
	sed -i '' "s|{SITELIBDIR}|${SITELIBDIR}|g" "${PKGTMP}/scripts/${POSTFLIGHT}"
	sed -i '' "s|{DATADIR}|${DATADIR}|g" "${PKGTMP}/scripts/${PREFLIGHT}"
	sed -i '' "s|{DATADIR}|${DATADIR}|g" "${PKGTMP}/scripts/${POSTFLIGHT}"
	# substitute in the bindir specified on the assumption that this is where
	# any old executables that have moved from bindir->sbindir should be
	# cleaned out from.
	sed -i '' "s|{BINDIR}|${BINDIR}|g" "${PKGTMP}/scripts/${PREFLIGHT}"
	sed -i '' "s|{BINDIR}|${BINDIR}|g" "${PKGTMP}/scripts/${POSTFLIGHT}"
	sed -i '' "s|{LAUNCHD}|${LAUNCHD}|g" "${PKGTMP}/scripts/${POSTFLIGHT}"
	# {pre,post}flight scripts must be 770 to execute
	chmod 0770 "${PKGTMP}/scripts/${PREFLIGHT}"
	chmod 0770 "${PKGTMP}/scripts/${POSTFLIGHT}"

	# add in M2Crypto if python version is less than 2.6
	if [[ ${PYMAJORVERSION} == 2 ]]; then if [[ ${PYMINORVERSION} -lt 6 ]]; then cp "M2Crypto-0.20.2-py2.5-macosx-10.5-ppc.egg" "${PKGROOT}/${SITELIBDIR}" && cp "easy-install.pth" "${PKGROOT}/${SITELIBDIR}"; fi ;  fi
	# add default bcfg2.conf
	mkdir -p "${PKGROOT}/etc"
	cp "${CONF}" "${PKGROOT}/etc/${CONF}"

	# add default launchd cron job
	mkdir -p "${PKGROOT}/Library/LaunchDaemons"
	cp "${LAUNCHD}" "${PKGROOT}/Library/LaunchDaemons/${LAUNCHD}"

client: prepare
	rm -rf `pwd`/bcfg2-${BCFGVER}.pkg
	echo "Building package"
	echo "Note that packagemaker is reknowned for spurious errors. Don't panic."
	"${PACKAGEMAKER}" --root "${PKGROOT}" \
			  --info "${PKGTMP}/${PROTO_PLIST}" \
			  --scripts "${PKGTMP}/scripts" \
			  ${FILTERS} \
			  --verbose \
			  --title "bcfg2" \
			  --out `pwd`/bcfg2-${BCFGVER}.pkg

server: prepare
	rm -rf `pwd`/bcfg2-${BCFGVER}.pkg
	echo "Building package"
	echo "Note that packagemaker is reknowned for spurious errors. Don't panic."
	"${PACKAGEMAKER}" --root "${PKGROOT}" \
			  --info "${PKGTMP}/${PROTO_PLIST}" \
			  --scripts "${PKGTMP}/scripts" \
			  --verbose \
			  --title "bcfg2" \
			  --out `pwd`/bcfg2-${BCFGVER}.pkg

clean:
	rm -rf bcfg2tmp bcfg2pkg
