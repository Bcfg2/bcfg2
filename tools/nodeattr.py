#!/usr/bin/python

from elementtree.ElementTree import XML, tostring
from pdis.xpath import compile as xcompile
from sys import argv

outputmode = argv[1]
attr = argv[2]

#this will need to be extrapolated from the bcfg2.conf file
#but for testing it can stay as is

xmlfile="testing.xml"
file=open(xmlfile, 'r').readlines()
myxmlfile=""
for line in file:
    myxmlfile+=line
metadata=XML(myxmlfile)
nodelist=[]

(level,searchterm)=attr.split("=")

if level.lower() == 'image':
    xexpression="/*/Client[@image='%s']"%searchterm
    path = xcompile(xexpression)
    nodelist += [ element.attrib['name'] for element in path.evaluate(metadata) ]
else:
    profilelist=[]
    if level.lower() == "profile":
        profilelist.append(searchterm)
    else:
        classlist=[]
        xexpression="/*/Profile"
        path=xcompile(xexpression)
        for profile in path.evaluate(metadata):
            if level.lower() == 'class':
                xexpression="/*/Class[@name='%s']"%searchterm
                path=xcompile(xexpression)
                if path.evaluate(profile) and profile.attrib['name'] not in profilelist:
                    profilelist.append(profile.attrib['name'])
            else:
                xexpression="/*/Class"
                path=xcompile(xexpression)
                for profclass in path.evaluate(profile):
                    xepression="/*/Class[@name='%s']"%profclass.attrib['name']
                    path = xcompile(xexpression)
                    for myclass in path.evaluate(metadata):
                        xexpression="/*/Bundle[@name='%s']"%searchterm
                        path=xcompile(xexpression)
                        if path.evaluate(myclass) and myclass.attrib['name'] not in classlist:
                            classlist.append(myclass.attrib['name'])
                xexpression="/*/Profile"
                path=xcompile(xexpression)
                for profile in path.evaluate(metadata):
                    for myclass in classlist:
                        xexpression="/*/Class[@name='%s']"%myclass
                        path=xcompile(xexpression)
                        if path.evaluate(profile) and profile.attrib['name'] not in profilelist:
                            profilelist.append(profile.attrib['name'])
                            
        for profile in profilelist:
            xexpression="/*/Client[@profile='%s']"%profile
            path = xcompile(xexpression)
            nodelist += [ element.attrib['name'] for element in path.evaluate(metadata) ]

if outputmode == '-c':
    print ",".join(nodelist)
if outputmode == '-n':
    for node in nodelist:
        print node
if outputmode == '-s':
    print "not yet implemented"

