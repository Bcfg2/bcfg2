#!/usr/bin/env python
# encoding: utf-8
"""
Environment.py

Classes for easy access to python environment information (e.g. python version).
"""

import sys
import os

class Pyversion():
	
    def __init__(self):
        # This is only helpful for Python 2 and older. Python 3 has sys.version_info.major.
        [self.major, self.minor, self.micro, self.releaselevel, self.serial] = sys.version_info
        self.version = sys.version
        self.hex = sys.hexversion


def main():
    # test class Pyversion
    pyversion = Pyversion()
    print "%s : %s" % ("major", pyversion.major)
    print "%s : %s" % ("minor", pyversion.minor)
    print "%s : %s" % ("micro", pyversion.micro)
    print "%s : %s" % ("releaselevel", pyversion.releaselevel)
    print "%s : %s" % ("serial", pyversion.serial)
    print "%s : %s" % ("version", pyversion.version)
    print "%s : %s" % ("hex", pyversion.hex)

    pass


if __name__ == '__main__':
    main()

