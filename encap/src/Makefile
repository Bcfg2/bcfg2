# $Id$

export SHELL = /bin/sh

.PHONY : test log all installconfig dist

log :
	( $(MAKE) all > ./make.log 2>&1 ) &

all :
	$(MAKE) -C ./encap-profiles all
	$(MAKE) -C ./bcfg2-site all
	$(MAKE) dist

installconfig :
	$(MAKE) -C ./bcfg2-site install
	
dist :
	
