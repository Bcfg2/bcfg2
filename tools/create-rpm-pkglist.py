#!/usr/bin/env python
#
# Copyright (c) 2010  Fabian Affolter, Bernewireless.net.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:

# * Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
# * Neither the name of the Bernewireless nor the names of its contributors
# may be used to endorse or promote products derived from this software
# without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ''AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Author: Fabian Affolter <fabian at bernewireless.net>
#

from lxml import etree
from optparse import OptionParser
import os
import yum

__author__ = 'Fabian Affolter <fabian@bernewireless.net>'
__version__ = '0.1'


def retrievePackages():
    """Getting the installed packages with yum."""
    yb = yum.YumBase()
    yb.conf.cache = os.geteuid() != 1
    pl = yb.doPackageLists('installed')
    pkglist = []
    for pkg in sorted(pl.installed):
        pkgdata = pkg.name, pkg.version
        pkglist.append(pkgdata)

    return pkglist


def parse_command_line_parameters():
    """Parses command line arguments."""
    usage = "usage: %prog [options]"
    version = 'Version: %prog ' + __version__
    parser = OptionParser(usage, version=version)
    parser.add_option("-s", "--show", action="store_true",
                      help="Prints the result to STOUT")
    parser.add_option("-v", "--pkgversion", action="store_true",
                      help="Include Package version")
    parser.add_option("-f", "--filename", dest="filename",
                      type="string",
                      metavar="FILE", default="packages.xml",
                      help="Write the output to an XML FILE")

    (options, args) = parser.parse_args()
    num_args = 1

    return options, args


def indent(elem, level=0):
    """Helps clean up the XML."""
    # Stolen from http://effbot.org/zone/element-lib.htm
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for e in elem:
            indent(e, level + 1)
            if not e.tail or not e.tail.strip():
                e.tail = i + "  "
        if not e.tail or not e.tail.strip():
            e.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def transformXML():
    """Transform the package list to an XML file."""
    packagelist = retrievePackages()
    root = etree.Element("PackageList")
    for i, j in packagelist:
        root.append(etree.Element("Package", name=i, version=j))
    #Print the content
    #print(etree.tostring(root, pretty_print=True))
    tree = etree.ElementTree(root)
    return tree


def main():
    options, args = parse_command_line_parameters()
    filename = options.filename
    packagelist = transformXML()

    if options.show == True:
        tree = etree.parse(filename)
        for node in tree.findall("//Package"):
            print(node.attrib["name"])
        indent(packagelist.getroot())
        packagelist.write(filename, encoding="utf-8")

    if options.pkgversion == True:
        tree = etree.parse(filename)
        for node in tree.findall("//Package"):
            print("%s-%s" % (node.attrib["name"], node.attrib["version"]))

#FIXME : This should be changed to the standard way of optparser
#FIXME : Make an option available to strip the version number of the pkg
    if options.pkgversion == None and options.show == None:
        indent(packagelist.getroot())
        packagelist.write(filename, encoding="utf-8")

if __name__ == "__main__":
    main()
