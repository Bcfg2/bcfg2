# -- generic Makefile for building RPM-based packages out of source
#    code control systems (git, cvs, svn)
#
# $Id: Makefile 46 2007-10-24 09:14:12Z robin $

.SUFFIXES:
.PHONY: clean mrclean distclean prepclean all default
.PHONY: rpm rpmdist buildrpm buildrpmdist
.PHONY: buildtarball buildtargz
.PHONY: builddir distdir prepbuildtarball
.PHONY: cvs-export git-export svn-export test-export
.PHONY: cvs-clean git-clean svn-clean test-clean

SCM_TYPE := git
SCM_PATH := ../
#CVSROOT := $(shell cat 2>/dev/null src/CVS/Root)
#SVN_PATH := $(shell svn info ${SCM_PATH} 2>/dev/null | awk '/^URL:/{print $$2}')
#SVN_REV := $(shell svn info ${SVN_PATH} 2>/dev/null | awk '/^Last Changed Rev:/{print $$4}')

PACKAGE := $(shell cat PACKAGE)
VERSION := $(shell cat VERSION)
RELEASE := $(shell cat RELEASE)
BASE_VER := ${VERSION}-${RELEASE}
CURRENT_PACKAGE := $(PACKAGE)-$(BASE_VER)
TARBALL := $(PACKAGE)-$(VERSION).tar

DIRNAME := $(shell echo $${PWD})
DIRBASE := $(shell basename $${PWD})


default: rpmdist

# -- the "rpmdist" target will build out of the SCM, but will
#    use the user's default build settings (which in many cases
#    is exposed as an RPM repository)
#
rpmdist: buildrpmdist distclean

buildrpmdist: specfile buildtargz
	@rpmbuild \
	  -ta ./build/$(TARBALL).gz

# -- the "rpm" target will build out of the SCM, but will leave
#    the resulting package in the relative ./build/ directory
#
rpm: buildrpm $(SCM_TYPE)-clean

# add "debug" to a target to see the values of all these vars
debug:
	echo SCM_TYPE: ${SCM_TYPE} && \
	echo SCM_PATH: ${SCM_PATH} && \
	echo SVN_PATH: ${SVN_PATH} && \
	echo SVN_REV : ${SVN_REV} && \
	echo PACKAGE : ${PACKAGE} && \
	echo VERSION : ${VERSION} && \
	echo RELEASE : ${RELEASE} && \
	echo BASE_VER: ${BASE_VER} && \
	echo CURRENT_PACKAGE: ${CURRENT_PACKAGE} && \
	echo TARBALL: ${TARBALL} && \
	echo DIRNAME: ${DIRNAME} && \
	echo DIRBASE: ${DIRBASE}

buildrpm: specfile buildtargz
	@rpmbuild \
	  --define "_rpmdir ./build/" \
	  --define "_sourcedir ./build/" \
	  --define "_srcrpmdir ./build/" \
 	  -ta ./build/$(TARBALL).gz

buildtarball: prepbuildtarball
	@tar \
	  --create \
	  --directory ./build/ \
	  --file      ./build/$(TARBALL) \
	  --exclude misc/bcfg2.spec \
	  ${CURRENT_PACKAGE}

buildtargz: buildtarball
	@gzip -c < ./build/$(TARBALL) > ./build/$(TARBALL).gz

# This target copies files that are not in svn into the build tree
prepbuildtarball: $(SCM_TYPE)-export
	@cp ${PACKAGE}.spec ./build/${CURRENT_PACKAGE}/redhat/ && \
		cp -R scripts ./build/${CURRENT_PACKAGE}/redhat/

specfile: $(PACKAGE).spec

# create the spec file from the .in file and put in the build tree
$(PACKAGE).spec: PACKAGE VERSION RELEASE $(PACKAGE).spec.in
	@sed	-e "s|@PACKAGE@|$(PACKAGE)|"	\
		-e "s|@VERSION@|$(VERSION)|"	\
		-e "s|@RELEASE@|$(RELEASE)|"	\
		$(PACKAGE).spec.in > $@
test-clean:
	@cd .. \
	  && rm "$(CURRENT_PACKAGE)"

test-export: builddir
	@cd .. \
	  && ln -snvf $(DIRBASE) $(CURRENT_PACKAGE) \
	  && tar \
	    --create \
	    --dereference \
	    --to-stdout \
	    --exclude "*.git*" \
	    --exclude "*.svn*" \
	    --exclude "*/CVS/*" \
	    --exclude "$(CURRENT_PACKAGE)/build/*" \
	      $(CURRENT_PACKAGE) \
	  | tar \
	    --extract \
	    --directory $(CURRENT_PACKAGE)/build/ \
	    --file -

git-export: builddir prepclean
	@cd ../ && git archive --format=tar --prefix=$(CURRENT_PACKAGE)/ HEAD \
	  | (cd redhat/build && tar xf -)

git-clean:
	@:

cvs-export: builddir prepclean
	@cd ./build/ \
	  && echo CURRENT_PACKAGE: ${CURRENT_PACKAGE} \
	  && echo CVSROOT: ${CVSROOT} \
	  && CVSROOT=${CVSROOT} cvs export -r HEAD -d$(CURRENT_PACKAGE) ${PACKAGE}

cvs-clean:
	@:

svn-export: builddir prepclean
	@cd ./build/ \
	  && svn export $(SVN_PATH) $(CURRENT_PACKAGE)

svn-clean:
	@rm -f bcfg2.spec 2>/dev/null || :

builddir:
	@mkdir -p ./build

distdir:
	@mkdir -p ./dist

prepclean:
	@rm -rf ./build/$(CURRENT_PACKAGE)*

clean:
	@rm -rf ./build/* ./dist/* 2>/dev/null || :

mrclean: clean

distclean: clean $(SCM_TYPE)-clean
	@rmdir ./build/ ./dist/ 2>/dev/null || :
