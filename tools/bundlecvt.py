#!/usr/bin/env python
# $Id: $

from os import listdir
from sys import argv
from elementtree.ElementTree import XML, Element, tostring

if __name__ == '__main__':
    bname = argv[1]
    translations = argv[2]
    tdata = {}
    
    for t in listdir(translations):
        data = XML(open("%s/%s"%(translations,t)).read())
        tdata[data.attrib['system']] = {'VConfig':{}, 'VPackage':{}, 'VService':{}, 'VFS':{}}
        for entry in data.getchildren():
            if entry.tag == 'Image':
                continue
            tdata[data.attrib['system']][entry.tag][entry.attrib['name']] = entry.getchildren()
    bundle = XML(open(bname).read())

    new = Element('Bundle', version='2.0', name=bundle.attrib['name'])

    for system in tdata.keys():
        b = Element("System", name=system)
        for entry in bundle.getchildren():
            try:
                map(b.append, tdata[system][entry.tag][entry.attrib['name']])
            except:
                pass
        new.append(b)
            
    print tostring(new)
        
