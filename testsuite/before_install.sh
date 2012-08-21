#!/bin/bash

# before_install script for Travis-CI

apt-get update -qq
if [[ "$WITH_OPTIONAL_DEPS" == "yes" ]]; then
    apt-get install -qq python-selinux python-pylibacl
fi
