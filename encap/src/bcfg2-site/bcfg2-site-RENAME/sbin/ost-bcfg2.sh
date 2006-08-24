#!/bin/sh

#
# ost-bcfg2.sh : Control bcfg2 client via ostiary (wrapper script)
# $Id$
#

umask 002
exec 2>&1

LOG="multilog t /usr/local/var/multilog/bcfg2-client-ostiary"
PATH=/usr/local/lib/bcfg2/bin:/command:/usr/local/bin:/usr/bin:/bin
export PATH

case $1 in
       dvqn) bcfg2 -d -v -q -n      | $LOG ;;
        dvn) bcfg2 -d -v -n         | $LOG ;;
        dvq) bcfg2 -d -v -q         | $LOG ;;
         dv) bcfg2 -d -v            | $LOG ;;
         vq) bcfg2 -v -q            | $LOG ;;
          v) bcfg2 -v               | $LOG ;; 
    restart) svc -t bcfg2-client    | $LOG ;; 
          *) printf "ERROR in $0\n" | $LOG ;; 
esac

exit 0