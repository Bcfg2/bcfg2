#!/usr/bin/env python

import lxml.etree
import sys

important = {'Package':['name', 'version'],
             'Service':['name', 'status'],
             'Directory':['name', 'owner', 'group', 'perms'],
             'SymLink':['name', 'to'],
             'ConfigFile':['name', 'owner', 'group', 'perms'],
             'Permissions':['name', 'perms'],
             'PostInstall':['name']}

def compare(new, old):
    for i in range(2): #this is hardcoded.. may be a better looping method
        for child in new.getchildren():
            equiv = old.xpath('%s[@name="%s"]' % (child.tag, child.get('name')))
            if not important.has_key(child.tag):
                print "tag type %s not handled" % (child.tag)
                continue
            if len(equiv) == 0:
                print "didn't find matching %s %s" % (child.tag, child.get('name'))
                continue
            elif len(equiv) >= 1:
                if child.tag == 'ConfigFile':
                    if child.text != equiv[0].text:
                        continue
                if [child.get(field) for field in important[child.tag]] == \
                   [equiv[0].get(field) for field in important[child.tag]]:
                    new.remove(child)
                    old.remove(equiv[0])
                else:
                    print "+", lxml.etree.tostring(child),
                    print "-", lxml.etree.tostring(equiv[0]),
    if len(old.getchildren()) == 0 and len(new.getchildren()) == 0:
        return True
    if new.tag == 'Independant':
        name = 'Indep'
    else:
        name = new.get('name')
    print name, ["%s.%s" % (child.tag, child.get('name')) for child in old.getchildren()],
    print ["%s.%s" % (child.tag, child.get('name')) for child in new.getchildren()]
    return False
    

if __name__ == '__main__':
    try:
        (new, old) = sys.argv[1:3]
    except IndexError:
        print "Usage: crosscheck.py <new> <old>"
        raise SystemExit

    new = lxml.etree.parse(new).getroot()
    old = lxml.etree.parse(old).getroot()
    for src in [new, old]:
        for bundle in src.findall('./Bundle'):
            if bundle.get('name')[-4:] == '.xml':
                bundle.set('name', bundle.get('name')[:-4])

    for bundle in new.findall('./Bundle'):
        equiv = old.xpath('Bundle[@name="%s"]' % (bundle.get('name')))
        if len(equiv) == 0:
            print "couldnt find matching bundle for %s" % bundle.get('name')
            continue
        if len(equiv) == 1:
            if compare(bundle, equiv[0]):
                new.remove(bundle)
                old.remove(equiv[0])
        else:
            print "dunno what is going on for bundle %s" % (bundle.get('name'))
    i1 = new.find('./Independant')
    i2 = old.find('./Independant')
    if compare(i1, i2):
        new.remove(i1)
        old.remove(i2)

    #print lxml.etree.tostring(new)
    #print lxml.etree.tostring(old)
