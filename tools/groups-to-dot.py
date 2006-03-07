#!/usr/bin/env python

'''This script generates graphviz diagrams using bcfg2 metadata'''
__revision__ = '$Revision $'

import lxml.etree, sys

colors = ['aquamarine', 'chartreuse', 'gold', 'magenta', 'indianred1', 'limegreen', 'midnightblue',
          'lightblue', 'limegreen']

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "Usage groups-to-dot.py <groupsfile>"
        raise SystemExit, 1
    groups = lxml.etree.parse(sys.argv[1]).getroot()
    categories = {'default':'grey83'}
    for group in groups.findall('Group'):
        if group.get('category', False):
            if not categories.has_key(group.get('category')):
                categories[group.get('category')] = colors.pop()
        
    print "digraph groups {"
    for group in groups.findall('Group'):
        color = categories[group.get('category', 'default')]
        if group.get('profile', 'false') == 'true':
            print '\tnode [style="filled,bold", fillcolor=%s];' % (color)
        else:
            print '\tnode [style="filled", fillcolor=%s];' % (color)
        print '\t"%s";' % (group.get('name'))

    for group in groups.findall('Group'):
        for parent in group.findall('Group'):
            print '\t"%s" -> "%s" ;' % (group.get('name'), parent.get('name'))
    print "}"
        
