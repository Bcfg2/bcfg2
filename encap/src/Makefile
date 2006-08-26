# $Id$

export SHELL = /bin/sh

.PHONY : test log all clean uninstall

log :
	@printf "Building in background, and logging to ./make.log\n"
	( $(MAKE) all > ./make.log 2>&1 ) &

all :
	$(MAKE) -C ./encap-profiles all
	$(MAKE) -C ./bcfg2-site all
	$(MAKE) -C ./makeself-dist all
	@printf "\n\n### encap build finished...\n"
	@printf "## Client install self-extracting/installing package is:\n"
	@printf "%s\n" "`ls makeself-dist/*.run 2>/dev/null`"
	@printf "# Use 'epkg -i <packagename>' to install encap packages...\n"
	@printf "## Doc encap packages are:\n"
	-@(ls encap-profiles/*doc*.tar.gz 2>/dev/null)
	@printf "## Server encap packages, if built (GNU/Linux only), are:\n"
	-@printf "%s\n" "`ls encap-profiles/bcfg2-glib-*.tar.gz 2>/dev/null`"
	-@printf "%s\n" "`ls encap-profiles/bcfg2-gamin-*.tar.gz 2>/dev/null`"
	-@printf "%s\n" "`ls encap-profiles/bcfg2-cheetah-[0-9]*.tar.gz 2>/dev/null`"
	@printf "\n"
    
clean :
	-rm ./*.log ./*~ ./\#*
	
uninstall : clean
	$(MAKE) -C ./encap-profiles uninstall
	$(MAKE) -C ./bcfg2-site distclean
	$(MAKE) -C ./makeself-dist distclean
