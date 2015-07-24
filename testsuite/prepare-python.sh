#!/bin/sh

if [ -n "$PYTHON" ]; then
    echo "Try to use custom python version: $PYTHON"
    pip install 'virtualenv<1.8'
    mkdir -p "$HOME/custom-virtualenv"
    virtualenv -p "python$PYTHON" --use-distribute "$HOME/custom-virtualenv"
fi
