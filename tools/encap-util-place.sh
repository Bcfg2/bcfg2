#!/bin/bash

# This puts encaps in the right directories, creating the
# directories if needed.

getdir(){
    case $1 in
	*"ix86-linux_debian_etch"*) printf "linux/debian/etch/ix86/" ;;
	*"ix86-linux_redhat_60"*) printf "linux/redhat/60/ix86/" ;;
	*"ix86-linux_redhat_72"*) printf "linux/redhat/72/ix86/" ;;
	*"ix86-linux_redhat_rhel4"*) printf "linux/redhat/rhel4/ix86/" ;;
	*"ix86-linux_suse_sles10"*) printf "linux/suse/sles10/ix86/" ;;
	*"ix86-linux_suse_sles8"*) printf "linux/suse/sles8/ix86/" ;;
	*"rs6000-aix4.3.1"*) printf "aix/4.3.1/rs6000/" ;;
	*"rs6000-aix4.3.3"*) printf "aix/4.3.3/rs6000/" ;;
	*"rs6000-aix5.2.0"*) printf "aix/5.2.0/rs6000/" ;;
	*"rs6000-aix5.3.0"*) printf "aix/5.3.0/rs6000/" ;;
	*"sparc-solaris10"*) printf "solaris/10/sparc/" ;;
	*"sparc-solaris8"*) printf "solaris/8/sparc/" ;;
	*"sparc-solaris9"*) printf "solaris/9/sparc/" ;;
	*"sparc-solaris2.6"*) printf "solaris/2.6/sparc/" ;;
	*"x86_64-linux_suse_sles10"*) printf "linux/suse/sles10/x86_64/" ;;
	*"-encap-share.tar.gz") printf "share/" ;;
	*) printf "ERROR" ;;
	esac
}

for ep in $(find . -type f | grep -v \.sh$ \
                           | grep -v epkg\.tar$ \
			   | grep -v "^\.\/xml\/"); do
	DIR="$(getdir $ep)"
	EPNAME="$(basename $ep)"
	if [ "${DIR}x" != "ERRORx" ]; then
	    if [ ! -d $DIR ]; then mkdir -p $DIR; fi
	    mv $ep $DIR 2>&1 | grep -v "are the same file"
	else
	    printf "ERROR: Don't know where to put $ep\n"
	fi
done

exit 0
