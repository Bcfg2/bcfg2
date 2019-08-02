#!/bin/bash -ex

# install script for Travis-CI
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
        pip_wheel pyinotify boto pylibacl Jinja2 cherrypy nose-show-skipped \
            google_compute_engine

        if [[ $PYVER == "2.6" ]]; then
            pip install \
                --global-option='build_ext' \
                --global-option='--include-dirs=/usr/include/x86_64-linux-gnu' \
                m2crypto

            pip_wheel 'django<1.7' 'South<0.8' 'mercurial<4.3' cheetah guppy \
                'pycparser<2.19' python-augeas 'PyYAML<5.1'
        else
            if [[ $PYVER == "2.7" ]]; then
                pip_wheel m2crypto guppy
            fi

            pip_wheel django mercurial cheetah3 python-augeas PyYAML
        fi
    fi
fi

# Use system site-packages and pymodules
if [[ "$WITH_SYSTEM_SITE_PACKAGES" == "yes" ]]; then
     cat <<EOF > "$SITE_PACKAGES/system-packages.pth"
/usr/lib/python$PYVER/site-packages/
/usr/lib/python$PYVER/dist-packages/
/usr/lib/pymodules/python$PYVER/
EOF
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
