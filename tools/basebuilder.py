#!/usr/bin/env python

from sys import argv
from elementtree.ElementTree import Element, SubElement, tostring

if __name__ == '__main__':
    dir = argv[1]
    imagename = dir.split('/')[-1]
    e = Element("Image", name=imagename)
    for line in open("%s/base.ConfigFile"%(dir)).readlines():
        SubElement(e, "ConfigFile", name=line.strip())
    for line in open("%s/base.Package"%(dir)).readlines():
        SubElement(e, "Package", name=line.strip())
    for line in open("%s/base.Service"%(dir)).readlines():
        SubElement(e, "Service", name=line.strip().split()[0])

    print tostring(e)
