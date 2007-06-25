# $Id$

.PHONY : test log all install clean distclean encaps rename
.SUFFIXES :
.SUFFIXES : .ep .installed .packaged .d

export BASEDIR = /usr/local
export ENCAPDIR := ${BASEDIR}/encap
export EPKG := ${BASEDIR}/bin/epkg
export MKENCAP := ${BASEDIR}/bin/mkencap
export SHELL = /bin/sh
srcdir = .
export EP2TARGET := $(srcdir)/ep2target
PAGER ?= more

BCFG2_CHEETAH_DOC := $(basename $(wildcard bcfg2-cheetah-doc-*.ep))
BCFG2_GAMIN := $(basename $(wildcard bcfg2-gamin-*.ep))
BCFG2_GLIB := $(basename $(wildcard bcfg2-glib-*.ep))
BCFG2_LIBXML2 := $(basename $(wildcard bcfg2-libxml2-*.ep))
BCFG2_LIBXSLT := $(basename $(wildcard bcfg2-libxslt-*.ep))
BCFG2_LXML := $(basename $(wildcard bcfg2-lxml-*.ep))
BCFG2_PYREX := $(basename $(wildcard bcfg2-pyrex-*.ep))
OSTIARTY_DOC := $(basename $(wildcard ostiary-doc-*.ep))

sources := $(BCFG2_CHEETAH_DOC) $(BCFG2_GAMIN) $(BCFG2_GLIB) $(BCFG2_LIBXML2) $(BCFG2_LIBXSLT) $(BCFG2_LXML) $(BCFG2_PYREX) $(OSTIARTY_DOC)

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
	$(EP2TARGET) $< > $@
	@printf "***** STOP .d.ep for |$*| ***** \n"

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
		for OLDNAME in `(ls . | grep .*-encap-.*.tar.gz) || break`; do \
			NEWNAME="`printf "%s\n" "$${OLDNAME}" \
				| awk -F- '{$$NF = "OSDIST.tar.gz" ; print}' \
				| sed s:\ :-:g | sed s:OSDIST:\$${OS}:g`" ; \
			if [ "$${OLDNAME}x" != "$${NEWNAME}x" ]; then \
				mv ./$${OLDNAME} ./$${NEWNAME}; \
			fi; \
		done; \
	fi
	for OLDNAME in `(ls . | grep .*-doc-.*-encap-.*.tar.gz) || break`; do \
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

include $(addsuffix .d,$(sources))
