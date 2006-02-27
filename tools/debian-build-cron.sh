#!/bin/sh
# rsync all the repo stuff to keep it up to date
# this pulls the debian repo from mirror.mcs.anl.gov if the currect sync is finished.
# If it isn't finished it will just back off and try again when the script runs next time.

if ! /root/bin/rsync-debian-repo ; then
    echo "repo not synced ";
fi

# now rebuild the local repo so that it will grab everything that was added today.
if ! /root/bin/local-deb-repo-maker ; then
    echo "local repos are not up to date ";
fi

#make a back up of the current pkglist so we can diff later
cp /disks/bcfg2/Pkgmgr/debian-sarge.xml /tmp/debian-sarge.xml.current

if /root/bin/create-debian-pkglist.pl ; then  
    diff /tmp/debian-sarge.xml.current /disks/bcfg2/Pkgmgr/debian-sarge.xml 
    rm -f /tmp/debian-sarge.xml.current

    #this is mainly cause this dies from time to time.. so this is protection
    /etc/init.d/apt-proxy restart
else
    echo "there was a problem with creating the new pkglist.xml";
    exit 1;
fi

#this was problem-matic so I found that it was more realiable to just make its 
#own cron job to restart every couple of days to reduce the memory consumption
#restart the server.. shouldn't be needed but memory leaks make it needed.
#/etc/init.d/bcfg2-server restart 

