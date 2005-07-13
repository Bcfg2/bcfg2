#!/usr/sfw/bin/gmake

VERS=0.6.8-2

default: clean package

package:
	-mkdir tmp tmp/bcfg2-server tmp/bcfg2
	-cd ../ && python setup.py install --prefix=$(PWD)
	-pkgmk -o -a `uname -m` -f prototype.bcfg2 -d $(PWD)/tmp -r $(PWD)
	-pkgmk -o -a `uname -m` -f prototype.bcfg2-server -d $(PWD)/tmp -r $(PWD)
	-pkgtrans -o -s $(PWD)/tmp $(PWD)/bcfg2-$(VERS) SCbcfg2
	-pkgtrans -o -s $(PWD)/tmp $(PWD)/bcfg2-server-$(VERS) SCbcfg2-server
	-gzip -f $(PWD)/bcfg2-$(VERS)
	-gzip -f $(PWD)/bcfg2-server-$(VERS)

clean: 
	-rm -rf tmp bin lib share
	-rm -rf bcfg2-$(VERS).gz bcfg2-server-$(VERS).gz

