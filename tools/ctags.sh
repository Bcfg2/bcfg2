#!/bin/bash

usage() {
    echo "$(basename $0) [-e] [-o <outfile>] [-s <source dir>]"
    echo "  -e: etags mode"
    echo "  -o <outfile>: Write to <outfile>. Default is tags or TAGS in the"
    echo "                default source dir"
    echo "  -s <source dir>: Find Bcfg2 source directory.  Default is the "
    echo "                   parent of the directory where $(basename $0) lives"
    exit 1
}

# compute the path to the parent directory of tools/
SRCDIR=$(pwd)/$(dirname $0)/..

CTAGS=ctags
ETAGS=
CTAGS_ARGS=
OUTFILE="$SRCDIR/TAGS"

while getopts ":eho:s:" opt; do
    case $opt in
        e)
            ETAGS=1
            CTAGS_ARGS="$CTAGS_ARGS -e"
            ;;
        h)
            usage
            ;;
        o)
            $OUTFILE=$OPTARG
            ;;
        s)
            $SRCDIR=$OPTARG
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            usage
            ;;
    esac
done

CTAGS_ARGS="$CTAGS_ARGS -f $OUTFILE"

find "$SRCDIR/testsuite" "$SRCDIR/tools" "$SRCDIR/src/lib" -name \*.py | \
    xargs "$CTAGS" $CTAGS_ARGS
find "$SRCDIR/src/sbin" | xargs "$CTAGS" $CTAGS_ARGS --append

