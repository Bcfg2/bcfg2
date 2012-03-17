#!/bin/sh

# This gets the encaps out of a makeself .run file

for RUN in $(find . -type f | grep run$); do
    DIR="$(dirname $RUN)"
    $RUN --noexec --keep --target $DIR
done

exit 0
