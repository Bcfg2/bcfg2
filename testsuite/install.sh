#!/bin/bash -ex

# Update package sources
sudo apt-get update

# Get python version
PYVER=$(python -c 'import sys;print(".".join(str(v) for v in sys.version_info[0:2]))')
SITE_PACKAGES=$(python -c 'from distutils.sysconfig import get_python_lib; print(get_python_lib())')

if [[ ${PYVER:0:1} == "2" && $PYVER != "2.7" && $PYVER != "2.6" ]]; then
    pip install --index-url=https://pypi.org/simple -r testsuite/requirements-legacy.txt
else
    pip install --upgrade pip

    pip_wheel() {
        pip wheel --find-links="$HOME/.cache/wheels/" --wheel-dir="$HOME/.cache/wheels/" "$@"
        pip install --no-index --find-links="$HOME/.cache/wheels/" "$@"
    }

    sudo apt-get install -y libxml2-dev libxml2-utils
    if [[ $PYVER == "2.6" ]]; then
        pip_wheel -r testsuite/requirements-26.txt
        pip_wheel unittest2
    else
        pip_wheel -r testsuite/requirements.txt

        if [[ ${PYVER:0:1} == "3" ]]; then
            # TODO: Move to "requirements.txt" if all the new errors are fixed.
            pip_wheel 'pylint>1.4'
        fi
    fi


    if [[ "$WITH_OPTIONAL_DEPS" == "yes" ]]; then
        sudo apt-get install -y libaugeas-dev libacl1-dev libssl-dev swig
        pip_wheel \
            Jinja2 \
            PyYAML \
            boto \
            cheetah3
            cherrypy \
            django \
            google_compute_engine \
            guppy \
            m2crypto \
            mercurial \
            nose-show-skipped \
            pyinotify \
            pylibacl \
            python-augeas \
    fi
fi

# Setup the local xml schema cache
download_schema() {
    if [[ ! -e "$1" ]]; then
        wget -O "$1" "$2"
    fi
}

mkdir -p "$HOME/.cache/xml/"
download_schema "$HOME/.cache/xml/XMLSchema.xsd" "http://www.w3.org/2001/XMLSchema.xsd"
download_schema "$HOME/.cache/xml/xml.xsd" "http://www.w3.org/2001/xml.xsd"

cat > "$HOME/.cache/xml/catalog.xml" <<EOF
<?xml version="1.0"?>
<catalog xmlns="urn:oasis:names:tc:entity:xmlns:xml:catalog">
  <system systemId="http://www.w3.org/2001/XMLSchema.xsd" uri="$HOME/.cache/xml/XMLSchema.xsd" />
  <system systemId="http://www.w3.org/2001/xml.xsd" uri="$HOME/.cache/xml/xml.xsd" />
  <nextCatalog catalog="/etc/xml/catalog.xml" />
</catalog>
EOF
