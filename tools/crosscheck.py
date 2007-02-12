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
                    print "%s %s contents differ" \
                          % (child.tag, child.get('name'))
                    continue
            noattrmatch = [field for field in important[child.tag] if \
                           child.get(field) != equiv[0].get(field)]
            if not noattrmatch:
                new.remove(child)
                old.remove(equiv[0])
            else:
                print "%s %s attributes %s do not match" % \
                      (child.tag, child.get('name'), noattrmatch)
    if len(old.getchildren()) == 0 and len(new.getchildren()) == 0:
        return True
    if new.tag == 'Independant':
        name = 'Indep'
    else:
        name = new.get('name')
    both = []
    oldl = ["%s %s" % (entry.tag, entry.get('name')) for entry in old]
    newl = ["%s %s" % (entry.tag, entry.get('name')) for entry in new]
    for entry in newl:
        if entry in oldl:
            both.append(entry)
            newl.remove(entry)
            oldl.remove(entry)
    for entry in both:
        print "%s differs (in bundle %s)" % (entry, name)
    for entry in oldl:
        print "%s only in old configuration (in bundle %s)" % (entry, name)
    for entry in newl:
        print "%s only in new configuration (in bundle %s)" % (entry, name)
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
