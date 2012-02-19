#!/bin/sh

# This builds the XML Pkgmgr files for the encap directory
# structure created by the place script. It assumes the 
# directory has a *.run file in it (from the bcfg2 encap build)

SITEBASEURI="http://example.com/encaps"

for RUN in $(find * -type f | grep run$); do 
    DIR="$(dirname $RUN)"
    FILE="$(basename $RUN)"
    ARCH="$(printf "$FILE" | awk -F\- '{print $4}')"
    OS="$(printf "$FILE" | awk -F\- '{print $5}' | sed s:\.run$::g)"
    case $OS in
	    *aix*) OSDIR="aix/$(printf "$OS" | sed s:aix::g)" ;;
        *solaris*) OSDIR="solaris/$(printf "$OS" | sed s:solaris::g)" ;;
	  *linux*) OSDIR="$(printf "$OS" | sed s:\_:\/:g)" ;;
                *) exit 1
    esac
    XML="./xml/site-encaps-${ARCH}-${OS}.xml"
    printf "<PackageList priority='0'\n" > $XML
    printf "             type='encap'\n" >> $XML
    printf "             uri='${SITEBASEURI}/%s/%s'>\n" "$OSDIR" "$ARCH" >> $XML
    printf "    <Group name='%s-%s'>\n" "$ARCH" "$OS" >> $XML
    for FILE in `(cd ./$DIR && ls *-encap-*.tar.gz) | sort`; do
	printf "        <Package file='%s'/>\n" "$FILE" >> $XML
    done
    printf "    </Group>\n" >> $XML
    printf "</PackageList>\n" >> $XML
done

exit 0
