#!/bin/bash

# install script for Travis-CI

pip install -r testsuite/requirements.txt --use-mirrors

PYVER=$(python -c 'import sys;print ".".join(str(v) for v in sys.version_info[0:2])')

if [[ "$WITH_OPTIONAL_DEPS" == "yes" ]]; then
    if [[ $PYVER == "2.5" ]]; then
        # markdown 2.2.0 is broken on py2.5, so until 2.2.1 is released use 2.1
        pip install --use-mirrors 'markdown<2.2'
        pip install --use-mirrors simplejson
    fi
    pip install --use-mirrors genshi cheetah 'django<1.4' South M2Crypto
else
    # python < 2.6 requires M2Crypto for SSL communication, not just
    # for encryption support
    if [[ $PYVER == "2.5" || $PYVER == "2.4" ]]; then
        pip install --use-mirrors M2crypto
    fi
fi
