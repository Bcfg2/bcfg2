#!/bin/bash

# This makes building our manpages easier and more consistent. More
# information about the tool used to do this can be found at:
#
# https://github.com/rtomayko/ronn

if [ ! -d man -o ! -d tools ]
then
    echo "Must be in the top-level bcfg2 source directory"
    exit 1
fi

for f in $(ls man)
do
    ronn -r --pipe tools/manpagegen/${f}.ronn | grep -iv ronn > man/${f}
done
