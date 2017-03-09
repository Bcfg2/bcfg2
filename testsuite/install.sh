#!/bin/bash -ex

# install script for Travis-CI

pip install -r testsuite/requirements.txt

PYVER=$(python -c 'import sys;print(".".join(str(v) for v in sys.version_info[0:2]))')

if [[ "$WITH_OPTIONAL_DEPS" == "yes" ]]; then
    pip install genshi PyYAML pyinotify boto 'django<1.5' pylibacl python-augeas

    if [[ ${PYVER:0:1} == "2" ]]; then
        # django supports py3k, but South doesn't, and the django bits
        # in bcfg2 require South
        pip install cheetah 'South<0.8'
        pip install m2crypto
    fi
fi
