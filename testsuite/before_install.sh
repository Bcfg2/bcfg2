#!/bin/bash

# before_install script for Travis-CI

sudo apt-get update -qq
sudo apt-get install -qq swig pylint libxml2-utils
if [[ "$WITH_OPTIONAL_DEPS" == "yes" ]]; then
    sudo apt-get install -qq python-selinux python-pylibacl python-pyinotify \
        python-yaml yum
fi
