#!/bin/sh
set -x
set -e
aclocal
automake -a -c --foreign
autoconf

