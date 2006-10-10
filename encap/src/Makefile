# $Id$

export SHELL = /bin/sh

.PHONY : test log all clean distclean uninstall

DEST ?= DIST
MKINSTALLDIRS = ./bcfg2-site/bcfg2-site-RENAME/mkinstalldirs

log :
	@printf "Building in background, and logging to ./make.log\n"
	( $(MAKE) all > ./make.log 2>&1 ) &

all :
	$(MAKE) -C ./encap-profiles all
	$(MAKE) -C ./bcfg2-site all
	$(MAKE) -C ./makeself-dist all
	if [ ! -d $(DEST) ]; then $(MKINSTALLDIRS) $(DEST); fi
	cp makeself-dist/*.run $(DEST)
	cp encap-profiles/*.tar.gz $(DEST)
	@printf "\n\n### encap build finished...\n"
	@printf "## Client install self-extracting/installing package is:\n"
	@printf "%s\n" "`ls $(DEST)/*.run 2>/dev/null`"
	@printf "\n"
    
clean :
	-rm ./*.log ./*~ ./\#*
	
distclean: clean
	-rm $(DEST)/*
	-rmdir $(DEST)
	
uninstall : clean
	$(MAKE) -C ./encap-profiles uninstall
	$(MAKE) -C ./bcfg2-site distclean
	$(MAKE) -C ./makeself-dist distclean
