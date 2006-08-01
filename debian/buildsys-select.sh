#!/bin/sh
#
# This script will select the build target, which is one of:
#   2.3 	- Build for python2.3
#   2.4		- Build for python2.4
#   pycentral	- Build with python-central support

FILES="control.in bcfg2.init bcfg2-server.init pycompat compat"
SUITE=$1

if [ ! -d buildsys ]; then
  echo "you need to be in debian/ directory"
  exit 1
fi

copy_files() {
  for i in $FILES; do
    if [ -e buildsys/$SUITE/$i ]; then
      cp buildsys/$SUITE/$i $i
    else
      cp buildsys/common/$i $i
    fi
  done
}

toggle_DPS() {
  case $1 in
    enable)
      sed -i -e 's/^#DEB_PYTHON_SYSTEM/DEB_PYTHON_SYSTEM/' rules
      ;;
    disable)
      sed -i -e 's/^DEB_PYTHON_SYSTEM/#DEB_PYTHON_SYSTEM/' rules
      ;;
    *)
      echo "internal error!"
      exit 1
      ;;
  esac
}

generate_control() {
  cp control.in control
  if [ "$SUITE" = "pycentral" ]; then
    toggle_DPS enable
  else
    toggle_DPS disable
  fi
  cd .. && DEB_AUTO_UPDATE_DEBIAN_CONTROL=yes fakeroot debian/rules clean
}

case $SUITE in
  2.3|2.4|pycentral)
    copy_files
    generate_control
    ;;
  clean)
    rm $FILES control
    toggle_DPS enable
    echo "removed build files, select a build system to enable build"
    ;;
  *)
    echo "Usage: $0 2.3|2.4|pycentral|clean"
    ;;
esac
