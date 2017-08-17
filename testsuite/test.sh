#!/bin/sh

NOSE_OPTS=""

if [ "$WITH_OPTIONAL_DEPS" = "yes" ]; then
    NOSE_OPTS="--show-skipped"
fi

exec nosetests $NOSE_OPTS testsuite
