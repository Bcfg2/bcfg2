#!/bin/bash

# install script for Travis-CI

pip install -r testsuite/requirements.txt --use-mirrors

PYVER=$(python -c 'import sys;print(".".join(str(v) for v in sys.version_info[0:2]))')

if [[ "$WITH_OPTIONAL_DEPS" == "yes" ]]; then
    pip install --use-mirrors genshi PyYAML pyinotify
    if [[ $PYVER == "2.5" ]]; then
        pip install --use-mirrors simplejson
    fi
    if [[ ${PYVER:0:1} == "2" ]]; then
        # django supports py3k, but South doesn't, and the django bits
        # in bcfg2 require South
        pip install cheetah django South M2Crypto
    fi
else
    # python < 2.6 requires M2Crypto for SSL communication, not just
    # for encryption support
    if [[ $PYVER == "2.5" || $PYVER == "2.4" ]]; then
        pip install --use-mirrors M2crypto
    fi
fi
