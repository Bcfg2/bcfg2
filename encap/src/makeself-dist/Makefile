# $Id$

# Variables
export SHELL = /bin/sh
export PATH = /usr/local/lib/bcfg2/bin:/usr/local/bin:/usr/bin:/bin

# Main

.PHONY : all clean distclean
.SUFFIXES : 

all : 
	chmod 755 ./makedist.sh && ./makedist.sh

clean :
	-rm ./*~ ./\#*

distclean : clean
	-rm -rf ./bcfg2-*
