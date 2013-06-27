#!/usr/bin/gmake

VERS=1.2.4-1
PYVERSION := $(shell python -c "import sys; print sys.version[0:3]")

default: clean package

package:
	-mkdir  tmp tmp/bcfg2-server tmp/bcfg2
	-mkdir -p build/lib/$(PYVERSION)/site-packages
	-cd ../ && PYTHONPATH=$(PYTHONPATH):$(PWD)/build/lib/python2.6/site-packages/ python setup.py install --single-version-externally-managed --record=/dev/null --prefix=$(PWD)/build/usr
	#setuptools appears to use a restictive umask
	-chmod -R o+r build/
	-chmod +x build/usr/bin/bcfg2
	-sh ./gen-manifests.sh

clean:
	-rm -rf tmp build
	-rm -rf MANIFEST.bcfg2
	-rm -rf MANIFEST.bcfg2-server
