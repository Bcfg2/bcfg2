#!/bin/bash -ex

# install script for Travis-CI

sudo apt-get update -qq
sudo apt-get install swig libxml2-utils

pip install -r testsuite/requirements.txt

PYVER=$(python -c 'import sys;print(".".join(str(v) for v in sys.version_info[0:2]))')

if [[ ${PYVER:0:1} == "2" && $PYVER != "2.7" ]]; then
    pip install unittest2
fi

if [[ "$WITH_OPTIONAL_DEPS" == "yes" ]]; then
    sudo apt-get install -y yum libaugeas0 augeas-lenses libacl1-dev libssl-dev

    pip install PyYAML pyinotify boto pylibacl django Jinja2 mercurial guppy
    easy_install https://fedorahosted.org/released/python-augeas/python-augeas-0.4.1.tar.gz

    if [[ ${PYVER:0:1} == "2" ]]; then
        # django supports py3k, but South doesn't, and the django bits
        # in bcfg2 require South
        pip install cheetah 'South<0.8'
        pip install m2crypto
    fi
fi
