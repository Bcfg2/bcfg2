#!/bin/sh
if /root/bin/rsync-debian-repo ; then
	mv /cluster/bcfg/images/debian-3.0/pkglist.xml /cluster/bcfg/images/debian-3.0/pkglist.xml.old;
	if /root/bin/create-debian-pkglist.pl ; then
		/etc/init.d/bcfgd restart
	else
		mv /cluster/bcfg/images/debian-3.0/pkglist.xml.old /cluster/bcfg/images/debian-3.0/pkglist.xml;
		echo "there was a problem with creating the new pkglist.xml";
		exit 1;
	fi
else
	echo "repo not synced and bcfg not updates";
	exit 1;
fi
exit 0;
