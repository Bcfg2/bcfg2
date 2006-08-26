# $Id$

export SHELL = /bin/sh

.PHONY : test log all clean uninstall

log :
	( $(MAKE) all > ./make.log 2>&1 ) &

all :
	$(MAKE) -C ./encap-profiles all
	$(MAKE) -C ./bcfg2-site all
	$(MAKE) -C ./makeself-dist all
    
clean :
	-rm ./*.log ./*~
	
uninstall : clean
	$(MAKE) -C ./encap-profiles uninstall
	$(MAKE) -C ./bcfg2-site distclean
	$(MAKE) -C ./makeself-dist distclean
