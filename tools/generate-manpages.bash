#!/bin/bash

# This makes building our manpages easier and more consistent.

if [ ! -d man -o ! -d tools -o ! -d doc ]
then
    echo "Must be in the top-level bcfg2 source directory"
    exit 1
fi

sphinx-build -b man -D copyright="" doc man
