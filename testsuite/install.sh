#!/bin/bash -x

# install script for Travis-CI

pip install -r testsuite/requirements.txt --use-mirrors

PYVER=$(python -c 'import sys;print(".".join(str(v) for v in sys.version_info[0:2]))')

if [[ "$WITH_OPTIONAL_DEPS" == "yes" ]]; then
    pip install --use-mirrors genshi PyYAML pyinotify boto 'django<1.5' \
        pylibacl
    easy_install https://fedorahosted.org/released/python-augeas/python-augeas-0.4.1.tar.gz
    easy_install http://downloads.sourceforge.net/project/python-selinux/python-selinux/2.16/python-selinux-2.16.tar.bz2
    if [[ ${PYVER:0:1} == "2" ]]; then
        # django supports py3k, but South doesn't, and the django bits
        # in bcfg2 require South
        pip install cheetah 'South<0.8' M2Crypto
    fi
fi
