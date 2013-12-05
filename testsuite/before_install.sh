#!/bin/bash -x

# before_install script for Travis-CI

PYVER=$(python -c 'import sys;print(".".join(str(v) for v in sys.version_info[0:2]))')

sudo apt-get update -qq
sudo apt-get install -qq swig libxml2-utils
if [[ "$WITH_OPTIONAL_DEPS" == "yes" ]]; then
    if [[ ${PYVER:0:1} == "2" ]]; then
        sudo apt-get install -y yum libaugeas0 augeas-lenses libacl1-dev \
            libssl-dev
    fi
fi
