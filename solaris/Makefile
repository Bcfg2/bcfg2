#!/usr/sfw/bin/gmake

PYTHON="/usr/local/bin/python"
VERS=1.3.0rc1-1
PYVERSION := $(shell $(PYTHON) -c "import sys; print sys.version[0:3]")

default: clean package

package:
	-mkdir  tmp tmp/bcfg2-server tmp/bcfg2
	-mkdir -p build/lib/$(PYVERSION)/site-packages
	-cd ../ && PYTHONPATH=$(PYTHONPATH):$(PWD)/build/lib/python2.6/site-packages/ $(PYTHON) setup.py install --single-version-externally-managed --record=/dev/null --prefix=$(PWD)/build
	#setuptools appears to use a restictive umask
	-chmod -R o+r build/
	-cat build/bin/bcfg2 | sed -e 's!/usr/bin/python!$(PYTHON)!' > build/bin/bcfg2.new && mv build/bin/bcfg2.new build/bin/bcfg2
	-chmod +x build/bin/bcfg2
	-sh ./gen-prototypes.sh
	-pkgmk -o -a `uname -m` -f prototype.bcfg2 -d $(PWD)/tmp -r $(PWD)/build
	-pkgmk -o -a `uname -m` -f prototype.bcfg2-server -d $(PWD)/tmp -r $(PWD)/build
	-pkgtrans -o -s $(PWD)/tmp $(PWD)/bcfg2-$(VERS) SCbcfg2
	-pkgtrans -o -s $(PWD)/tmp $(PWD)/bcfg2-server-$(VERS) SCbcfg2-server
	-gzip -f $(PWD)/bcfg2-$(VERS)
	-gzip -f $(PWD)/bcfg2-server-$(VERS)

clean:
	-rm -rf tmp build
	-rm -rf bcfg2-$(VERS).gz bcfg2-server-$(VERS).gz
	-rm -rf prototype.bcfg2.fixed prototype.bcfg2-server.fixed
	-rm -f prototype.*
