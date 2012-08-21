#!/bin/bash

# install script for Travis-CI

pip install -r testsuite/requirements.txt --use-mirrors

if [[ "$WITH_OPTIONAL_DEPS" == "yes" ]]; then
    pip install --use-mirrors genshi cheetah 'django<1.4' M2Crypto
else
    # python < 2.6 requires M2Crypto for SSL communication, not just
    # for encryption support
    PYVER=$(python -c 'import sys;print ".".join(str(v) for v in sys.version_info[0:2])')
    if [[ $PYVER == "2.5" || $PYVER == "2.4" ]]; then
        pip install --use-mirrors M2crypto
    fi
fi
