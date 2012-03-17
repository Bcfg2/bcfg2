#!/bin/sh

# This shows a count of encap packages per directory
# Can be useful to make sure you have everything
# built for all platforms. It assumes the directory
# has a *.run file in it (from the bcfg2 encap build)

for RUN in $(find . -type f | grep run$); do 
    DIR="$(dirname $RUN)"
    printf "${DIR}: "
    (cd $DIR && ls | wc -l)
done

exit 0
