#!/usr/bin/env python

'''This script generates graphviz diagrams using bcfg2 metadata'''
__revision__ = '$Revision$'

import lxml.etree, sys

colors = ['aquamarine', 'chartreuse', 'gold', 'magenta', 'indianred1', 'limegreen', 'midnightblue',
          'lightblue', 'limegreen']

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "Usage groups-to-dot.py [-h] <metadatadir>"
        raise SystemExit, 1
    groups = lxml.etree.parse(sys.argv[-1] + '/groups.xml').getroot()
    clients= lxml.etree.parse(sys.argv[-1] + '/clients.xml').getroot()
    categories = {'default':'grey83'}
    instances = {}
    for group in groups.findall('Group'):
        if group.get('category', False):
            if not categories.has_key(group.get('category')):
                categories[group.get('category')] = colors.pop()
        
    print "digraph groups {"
    if '-h' in sys.argv:
        print '\trankdir="LR";'
        for client in clients.findall('Client'):
            if instances.has_key(client.get('profile')):
                instances[client.get('profile')].append(client.get('name'))
            else:
                instances[client.get('profile')] = [client.get('name')]
        for profile, clist in instances.iteritems():
            clist.sort()
            print '''\t"%s-instances" [ label="%s", shape="record" ];''' % (profile, '|'.join(clist))
            print '''\t"%s-instances" -> "%s";''' % (profile, profile)

    if '-b' in sys.argv:
        bundles = []
        [bundles.append(bund.get('name')) for bund in groups.findall('.//Bundle')
         if bund.get('name') not in bundles]
        bundles.sort()
        for bundle in bundles:
            print '''\t"%s" [ shape="rect"];''' % (bundle)
        
    for group in groups.findall('Group'):
        color = categories[group.get('category', 'default')]
        if group.get('profile', 'false') == 'true':
            print '\t"%s" [style="filled,bold", fillcolor=%s];' % (group.get('name'), color)
        else:
            print '\t"%s" [style="filled", fillcolor=%s];' % (group.get('name'), color)
        if '-b' in sys.argv:
            for bundle in group.findall('Bundle'):
                print '\t"%s" -> "%s";' % (group.get('name'), bundle.get('name'))
        
    for group in groups.findall('Group'):
        for parent in group.findall('Group'):
            print '\t"%s" -> "%s" ;' % (group.get('name'), parent.get('name'))
    print "}"
        
