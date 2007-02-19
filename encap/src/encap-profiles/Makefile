# $Id$

.PHONY : test log all install clean distclean uninstall encaps rename bcfg2only bcfg2bump
.SUFFIXES :
.SUFFIXES : .ep .sh .installed .packaged .d

export BASEDIR = /usr/local
export ENCAPDIR := ${BASEDIR}/encap
export EPKG := ${BASEDIR}/bin/epkg
export MKENCAP := ${BASEDIR}/bin/mkencap
export SHELL = /bin/sh
srcdir = .
export EP2TARGET := $(srcdir)/ep2target
PAGER ?= more

BCFG2 := $(basename $(wildcard bcfg2-[0-9].[0-9]*.ep))
BCFG2_CHEETAH := $(basename $(wildcard bcfg2-cheetah-[0-9].[0-9]*.ep))
BCFG2_CHEETAH_DOC := $(basename $(wildcard bcfg2-cheetah-doc-*.ep))
BCFG2_ELEMENTTREE := $(basename $(wildcard bcfg2-elementtree-*.ep))
BCFG2_GAMIN := $(basename $(wildcard bcfg2-gamin-*.ep))
BCFG2_GLIB := $(basename $(wildcard bcfg2-glib-*.ep))
BCFG2_GZIP := $(basename $(wildcard bcfg2-gzip-*.ep))
BCFG2_LIBXML2 := $(basename $(wildcard bcfg2-libxml2-*.ep))
BCFG2_LIBXSLT := $(basename $(wildcard bcfg2-libxslt-*.ep))
BCFG2_LXML := $(basename $(wildcard bcfg2-lxml-*.ep))
BCFG2_OPENSSL := $(basename $(wildcard bcfg2-openssl-*.ep))
BCFG2_PKG_CONFIG := $(basename $(wildcard bcfg2-pkg-config-*.ep))
BCFG2_PYOPENSSL := $(basename $(wildcard bcfg2-pyopenssl-*.ep))
BCFG2_PYREX := $(basename $(wildcard bcfg2-pyrex-*.ep))
BCFG2_PYTHON := $(basename $(wildcard bcfg2-python-[0-9].[0-9]*.ep))
BCFG2_READLINE := $(basename $(wildcard bcfg2-readline-*.ep))
BCFG2_ZLIB := $(basename $(wildcard bcfg2-zlib-*.ep))
DAEMONTOOLS := $(basename $(wildcard daemontools-[0-9].[0-9]*.ep))
DAEMONTOOLS_DOC := $(basename $(wildcard daemontools-doc-*.ep))
M4 := $(basename $(wildcard m4-*.sh))
MAKESELF := $(basename $(wildcard makeself-*.ep))
OSTIARTY := $(basename $(wildcard ostiary-[0-9].[0-9]*.ep))
OSTIARTY_DOC := $(basename $(wildcard ostiary-doc-*.ep))
PATCH := $(basename $(wildcard patch-*.ep))

sources_ep := $(sort $(BCFG2) $(BCFG2_CHEETAH) $(BCFG2_ELEMENTTREE) $(BCFG2_GZIP) $(BCFG2_OPENSSL) $(BCFG2_PKG_CONFIG) $(BCFG2_PYOPENSSL) $(BCFG2_PYTHON) $(BCFG2_READLINE) $(BCFG2_ZLIB) $(DAEMONTOOLS) $(MAKESELF) $(OSTIARTY) $(PATCH))

sources_sh := $(sort $(M4))

sources_server := $(sort $(BCFG2_GLIB) $(BCFG2_GAMIN) $(BCFG2_LIBXML2) $(BCFG2_LIBXSLT) $(BCFG2_LXML) $(BCFG2_CHEETAH_DOC) $(BCFG2_PYREX) $(DAEMONTOOLS_DOC) $(OSTIARTY_DOC))

# Only compile bcfg2-glib and bcfg2-gamin (needed by bcfg2 server) on Linux
# (Gamin only supports Linux), and only compile bcfg2-python-apt on known
# Debian and Ubuntu systems (as python-apt is distribution-specific)
UNAME := $(shell uname)

ifeq ($(UNAME),Linux)
DISTRO := $(shell cat /etc/issue | grep ^[a-zA-Z] | head -1)
endif

ifeq ($(DISTRO),Debian GNU/Linux 3.1 \n \l)
sources_ep += $(sources_server)
BCFG2_PYTHON_APT = bcfg2-python-apt-0.5.10
OS ?= linux_debian_sarge
endif

ifeq ($(DISTRO),Debian GNU/Linux 4.0 \n \l)
BCFG2_PYTHON_APT = bcfg2-python-apt-0.6.19
OS ?= linux_debian_etch
endif

ifeq ($(DISTRO),Debian GNU/Linux testing/unstable \n \l)
BCFG2_PYTHON_APT = bcfg2-python-apt-0.6.19
OS ?= linux_debian_sid
endif

ifeq ($(DISTRO),Ubuntu 6.06.1 LTS \n \l)
BCFG2_PYTHON_APT = bcfg2-python-apt-0.6.16.2ubuntu8
OS ?= linux_ubuntu_dapper
endif

ifeq ($(DISTRO),Red Hat Linux release 6.0 (Hedwig))
OS ?= linux_redhat_60
endif

ifeq ($(DISTRO),Red Hat Linux release 7.2 (Enigma))
OS ?= linux_redhat_72
endif

ifeq ($(DISTRO),Welcome to SuSE SLES 8 (powered by UnitedLinux 1.0) (i586))
OS ?= linux_suse_sles8
endif

ifeq ($(DISTRO),Welcome to SUSE Linux Enterprise Server 10 (i586) - Kernel \r (\l).)
OS ?= linux_suse_sles10
endif

ifdef BCFG2_PYTHON_APT
sources_ep += $(BCFG2_PYTHON_APT)
endif

# List of all sources...
sources := $(sort $(sources_ep) $(sources_sh))

%.installed : %.ep # Clean, compile and install an encap package
	@printf "***** START .ep.installed for |$*| ***** \n"
	-$(EPKG) -q -r $(ENCAPDIR)/$*
	-rm -rf $(ENCAPDIR)/$*
	-$(MKENCAP) -m /usr/local/bin/m4 -b -DUP $(srcdir)/$*.ep > ./$*.log 2>&1
	-$(MKENCAP) -m /usr/local/bin/m4 -b -T $(srcdir)/$*.ep >> ./$*.log 2>&1
	$(MKENCAP) -m /usr/local/bin/m4 -b -CBI $(srcdir)/$*.ep >> ./$*.log 2>&1
	$(EPKG) -q -i $(ENCAPDIR)/$*
	test -h $(BASEDIR)/var/encap/$*
	touch ./$*.installed
	@printf "***** STOP .ep.installed for |$*| ***** \n"

%.installed : %.sh # Create and install a "fake" encap package
	@printf "***** START .sh.installed for |$*| ***** \n"
	-$(EPKG) -q -r $(ENCAPDIR)/$*
	-rm -rf $(ENCAPDIR)/$*
	chmod 755 $(srcdir)/$*.sh && $(srcdir)/$*.sh
	$(EPKG) -q -i $(ENCAPDIR)/$*
	test -h $(BASEDIR)/var/encap/$*
	touch ./$*.installed
	@printf "***** STOP .sh.installed for |$*| ***** \n"

%.packaged : %.installed # Create .tar.gz encap packages
	@printf "***** START .installed.packaged for |$*| ***** \n"
	-rm $(ENCAPDIR)/$*-*.tar.gz
	-(cd $(ENCAPDIR) && $(MKENCAP) -e $*)
	-(cd $(ENCAPDIR) && $(MKENCAP) -c $*)
	mv $(ENCAPDIR)/$*-encap-*.tar.gz ./
	touch ./$*.packaged
	@printf "***** STOP .installed.packaged for |$*| ***** \n"

%.d : %.ep # Create dependancy files from .ep files
	@printf "***** START .d.ep for |$*| ***** \n"
	chmod 755 $(EP2TARGET) && $(EP2TARGET) $< > $@
	@printf "***** STOP .d.ep for |$*| ***** \n"

%.d : %.sh # Create dependancy files from .sh files
	@printf "***** START .d.sh for |$*| ***** \n"
	chmod 755 $(EP2TARGET) && $(EP2TARGET) $< > $@
	@printf "***** STOP .d.sh for |$*| ***** \n"

log :
	( $(MAKE) install > ./make.log 2>&1 \
	&& $(MAKE) encaps >> ./make.log 2>&1 \
	&& $(MAKE) rename >> ./make.log 2>&1 ) &

all : install encaps rename

.DELETE_ON_ERROR : # delete the target of a rule if it has changed and its
                   # commands exit with a nonzero exit status

install : $(EPKG) $(MKENCAP) $(EP2TARGET) $(M4).installed $(addsuffix .installed,$(sources))

encaps : $(EPKG) $(MKENCAP) $(EP2TARGET) $(addsuffix .packaged,$(sources))

rename : encaps
	if [ "$(OS)x" != "x" ]; then OS="$(OS)"; fi && \
	if [ "$${OS}x" != "x" ]; then \
		for OLDNAME in `(ls . | grep *-encap-*.tar.gz) || break`; do \
			NEWNAME="`printf "%s\n" "$${OLDNAME}" \
				| awk -F- '{$$NF = "OSDIST.tar.gz" ; print}' \
				| sed s:\ :-:g | sed s:OSDIST:\$${OS}:g`" ; \
			if [ "$${OLDNAME}x" != "$${NEWNAME}x" ]; then \
				mv ./$${OLDNAME} ./$${NEWNAME}; \
			fi; \
		done; \
	fi
	
	for OLDNAME in `(ls . | grep *-doc-*-encap-*.tar.gz) || break`; do \
		NEWNAME="`printf "%s\n" "$${OLDNAME}" \
			| awk -F- '{$$NF = "OSDIST.tar.gz" ; print}' \
			| sed s:\ :-:g | sed s:OSDIST:share:g`" ; \
		if [ "$${OLDNAME}x" != "$${NEWNAME}x" ]; then \
			mv ./$${OLDNAME} ./$${NEWNAME}; \
		fi; \
	done;

clean :
	-(rm ./*.log; rm ./*.packaged; rm ./*.gz; rm ./*~)

distclean : clean
	-rm ./*.d

uninstall : distclean
	-(find $(BASEDIR)/lib/bcfg2 | grep "\.pyc" | xargs -n1 rm)
	-(ENCAPS="m4 patch daemontools makeself ostiary bcfg2"; \
	for ENCAP in $${ENCAPS}; do \
		$(EPKG) -q -r $(ENCAPDIR)/$${ENCAP}-*; \
		rm -rf $(ENCAPDIR)/$${ENCAP}-*; \
		rm ./$${ENCAP}-*.installed; \
	done)
	-rm -rf  $(BASEDIR)/lib/bcfg2

bcfg2only :
	$(MAKE) -t; sleep 2; touch $(srcdir)/$(BCFG2).ep; $(MAKE)

bcfg2bump :
	@if [ "$(NEW)x" != "x" ]; then NEW="$(NEW)"; fi && \
	if [ "$(OLD)x" != "x" ]; then OLD="$(OLD)"; fi && \
	if [ "$(FORCE)x" != "x" ]; then FORCE="$(FORCE)"; fi && \
	if [ "$${OLD}x" != "x" -a "$${NEW}x" != "x" ]; then \
	OLDBASE="`printf "%s\n" "$${OLD}" | sed 's:\.ep::g'`"; \
	NEWBASE="`printf "%s\n" "$${NEW}" | sed 's:\.ep::g'`"; \
		if [ "$${FORCE}x" != "yesmamx" ]; then \
			printf "About to 'svn mv %s %s'\n" "$$OLD" "$$NEW"; \
			printf "\tand edit the later as appropriate.\n"; \
			printf "And then 'rm %s%s'...\n" "$$OLDBASE" ".*"; \
			printf "Press 'return' to continue, or 'ctrl-c' to exit. "; \
			read THROWAWAY; \
		fi; \
		svn mv $${OLD} $${NEW} && \
		sed s:$${OLDBASE}:$${NEWBASE}:g $${NEW} > $${NEW}.tmp && \
		mv $${NEW}.tmp $${NEW} && \
		rm $${OLDBASE}.*; \
		printf "Changes to %s are:\n" "$${NEW}"; \
		if [ "$${FORCE}x" != "yesmamx" ]; then \
			svn diff $${NEW} | $(PAGER); \
			printf "'svn commit %s %s -m \"EncapPackages: Bumped bcfg2 .ep version to %s\"'? \n" "$${OLD}" "$${NEW}" "$${NEW}"; \
			printf "Press 'return' to commit, or 'ctrl-c' to exit. "; \
			read THROWAWAY; \
		else \
			svn diff $${NEW}; \
		fi; \
		svn commit $${OLD} $${NEW} -m "EncapPackages: Bumped bcfg2 .ep version to $${NEW}"; \
	else \
		printf "Set the OLD, NEW (and optionally FORCE) environment "; \
		printf "variables. Example:\n"; \
		printf "\tOLD=bcfg2-0.8.3pre5.ep NEW=bcfg2-0.8.3.ep $(MAKE) bcfg2bump\n";\
	fi

include $(addsuffix .d,$(sources))
