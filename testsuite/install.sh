#!/bin/bash -ex

# Update package sources
sudo apt-get update
sudo apt-get install -y libxml2-dev libxml2-utils

# Get python version
PYVER=$(python -c 'import sys;print(".".join(str(v) for v in sys.version_info[0:2]))')

if [[ ${PYVER:0:1} == "2" && $PYVER != "2.7" && $PYVER != "2.6" ]]; then
    pip install --index-url=https://pypi.org/simple -r testsuite/requirements-legacy.txt
elif [[ "$PYVER" == "2.6" ]]; then
    pip install --index-url=https://pypi.org/simple -r testsuite/requirements.txt
else
    if [[ "$PYVER" == "2.7" ]]; then
        pip install --upgrade 'pip<21'
    else
        pip install --upgrade pip
    fi

    pip_wheel() {
        pip wheel --find-links="$HOME/.cache/wheels/" --wheel-dir="$HOME/.cache/wheels/" "$@"
        pip install --no-index --find-links="$HOME/.cache/wheels/" "$@"
    }

    pip_wheel -r testsuite/requirements.txt

    if [[ "$WITH_OPTIONAL_DEPS" == "yes" ]]; then
        sudo apt-get install -y libaugeas-dev libacl1-dev libssl-dev swig
        pip_wheel -r testsuite/requirements-optional.txt
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
