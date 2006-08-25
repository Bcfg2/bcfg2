# $Id$

# Variables

PATH = /usr/local/lib/bcfg2/bin:/usr/local/bin:/usr/bin:/bin
CHEETAH = /usr/local/lib/bcfg2/bin/cheetah

# Main

.PHONY : all clean distclean fill copy fix encap install test cheetah
.SUFFIXES : 

BD = /usr/local
ED = ${BD}/encap
export ED

all : encap

clean :
	for DIR in `find . -type d | grep -v "\.svn"`; do \
		for GLOB in \#\* \*\~ \*.out\*; do \
			(rm $${DIR}/$${GLOB} 2>/dev/null || true); \
		done; \
	done

distclean : clean
	-rm *-encap-*.tar.gz

fill : clean
	$(CHEETAH) fill -R --oext out

copy : fill
	EN=`cat bcfg2-site-RENAME/encapname.out` && \
	( test ! -d $(ED)/bcfg2-site-$${EN} || rm -rf $(ED)/bcfg2-site-$${EN} ) && \
	for SRC in `find bcfg2-site-RENAME | grep -v svn | grep -v tmpl`; do \
		DEST=$(ED)/`printf "%s\n" "$$SRC" | sed s/RENAME/$$EN/g | sed s/\.out//g`; \
		if [ -d $$SRC ]; then mkdir $$DEST; else cp $$SRC $$DEST; fi; \
	done		

fix : copy
	EN="$(ED)/bcfg2-site-`cat bcfg2-site-RENAME/encapname.out`" && \
	chown -R 0 $$EN && chgrp -R 0 $$EN && \
	find $$EN -type d | xargs -n1 chmod 0755 && \
	find $$EN -type f | xargs -n1 chmod 0644 && \
	chmod 0600 $$EN/etc/ostiary.cfg && \
	chmod 0600 $$EN/etc/bcfg2.conf && \
	chmod 0755 $$EN/sbin/ost-bcfg2.sh && \
	chmod 0755 $$EN/postinstall

encap : fix
	EN="bcfg2-site-`cat bcfg2-site-RENAME/encapname.out`" && \
	cd $(ED) && \
	( test ! -f $${EN}-encap-*.tar.gz || rm $${EN}-encap-*.tar.gz ) && \
	mkencap -c $$EN
	EN="bcfg2-site-`cat bcfg2-site-RENAME/encapname.out`" && \
	mv $(ED)/$${EN}-encap-*.tar.gz ./
    
install : fix
	-(EN="bcfg2-site-`cat bcfg2-site-RENAME/encapname.out`" && \
	epkg -q -r $(ED)/$$EN)
	EN="bcfg2-site-`cat bcfg2-site-RENAME/encapname.out`" && \
	cd $(ED) && \
	epkg -q -i $(ED)/$$EN && \
	test -h $(BD)/var/encap/$$EN

test :
	: $(PATH)
	$(CHEETAH) test
	
cheetah :
	$(CHEETAH) $(ARGS)
