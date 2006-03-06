#!/bin/bash

CWD=`pwd`
echo $CWD

cd debian/

#get the default python version for this system.
VERSION=`python -c 'import sys;major,minor = sys.version_info[0:2]; print minor '`

#hardcoded version is 2.3

if [ ${VERSION} -eq 4 ]; then

#fix all the files that are version specific

 for fd in bcfg2.install bcfg2.postinst.debhelper bcfg2-server.install bcfg2-server.posti\nst.debhelper;
 do
    sed -e 's/2\.3/2\.4/g' $fd > /tmp/${fd}.tmp
    mv /tmp/${fd}.tmp $fd
    #rm /tmp/${fd}.tmp
 done

fi

cd $CWD
