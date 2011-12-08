#!/usr/sfw/bin/gmake

PYTHON="/opt/csw/bin/python"
VERS=1.2.0-1
PYVERSION := $(shell $(PYTHON) -c "import sys; print sys.version[0:3]")

default: clean package

package:
	-mkdir tmp tmp/bcfg2-server tmp/bcfg2
	-cd ../ && $(PYTHON) setup.py install --prefix=$(PWD)
	-cat bin/bcfg2 | sed -e 's!/usr/bin/python!$(PYTHON)!' > bin/bcfg2.new && mv bin/bcfg2.new bin/bcfg2
	# Set python version to whichever version is installed
	-cat prototype.bcfg2 | sed -e 's!PYVERSION!python$(PYVERSION)!' > prototype.bcfg2.fixed
	-cat prototype.bcfg2-server | sed -e 's!PYVERSION!python$(PYVERSION)!' > prototype.bcfg2-server.fixed
	-pkgmk -o -a `uname -m` -f prototype.bcfg2.fixed -d $(PWD)/tmp -r $(PWD)
	-pkgmk -o -a `uname -m` -f prototype.bcfg2-server.fixed -d $(PWD)/tmp -r $(PWD)
	-pkgtrans -o -s $(PWD)/tmp $(PWD)/bcfg2-$(VERS) SCbcfg2
	-pkgtrans -o -s $(PWD)/tmp $(PWD)/bcfg2-server-$(VERS) SCbcfg2-server
	-gzip -f $(PWD)/bcfg2-$(VERS)
	-gzip -f $(PWD)/bcfg2-server-$(VERS)

clean:
	-rm -rf tmp bin lib share
	-rm -rf bcfg2-$(VERS).gz bcfg2-server-$(VERS).gz
	-rm -rf prototype.bcfg2.fixed prototype.bcfg2-server.fixed
