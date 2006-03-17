#!/usr/bin/env python

'''This script generates graphviz diagrams using bcfg2 metadata'''
__revision__ = '$Revision$'

import lxml.etree, sys, popen2

colors = ['aquamarine', 'chartreuse', 'gold', 'magenta', 'indianred1', 'limegreen', 'midnightblue',
          'lightblue', 'limegreen']

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "Usage groups-to-dot.py [-h] -o <outputfile> <metadatadir>"
        raise SystemExit, 1
    groups = lxml.etree.parse(sys.argv[-1] + '/groups.xml').getroot()
    clients = lxml.etree.parse(sys.argv[-1] + '/clients.xml').getroot()
    dotpipe = popen2.Popen4("dot -Tpng")
    categories = {'default':'grey83'}
    instances = {}
    for group in groups.findall('Group'):
        if group.get('category', False):
            if not categories.has_key(group.get('category')):
                categories[group.get('category')] = colors.pop()
        
    dotpipe.tochild.write("digraph groups {\n")
    if '-h' in sys.argv:
        dotpipe.tochild.write('\trankdir="LR";\n')
        for client in clients.findall('Client'):
            if instances.has_key(client.get('profile')):
                instances[client.get('profile')].append(client.get('name'))
            else:
                instances[client.get('profile')] = [client.get('name')]
        for profile, clist in instances.iteritems():
            clist.sort()
            dotpipe.tochild.write('''\t"%s-instances" [ label="%s", shape="record" ];\n''' % (profile, '|'.join(clist)))
            dotpipe.tochild.write('''\t"%s-instances" -> "group-%s";\n''' % (profile, profile))

    if '-b' in sys.argv:
        bundles = []
        [bundles.append(bund.get('name')) for bund in groups.findall('.//Bundle')
         if bund.get('name') not in bundles]
        bundles.sort()
        for bundle in bundles:
            dotpipe.tochild.write('''\t"bundle-%s" [ label="%s", shape="rect"];\n''' % (bundle, bundle))
        
    for group in groups.findall('Group'):
        color = categories[group.get('category', 'default')]
        if group.get('profile', 'false') == 'true':
            style="filled, bold"
        else:
            style = "filled"
        dotpipe.tochild.write('\t"group-%s" [label="%s", style="%s", fillcolor=%s];\n' %
                              (group.get('name'), group.get('name'), style, color))
        if '-b' in sys.argv:
            for bundle in group.findall('Bundle'):
                dotpipe.tochild.write('\t"group-%s" -> "bundle-%s";\n' %
                                      (group.get('name'), bundle.get('name')))
        
    for group in groups.findall('Group'):
        for parent in group.findall('Group'):
            dotpipe.tochild.write('\t"group-%s" -> "group-%s" ;\n' %
                                  (group.get('name'), parent.get('name')))
    dotpipe.tochild.write("}\n")
    dotpipe.tochild.close()
    data = dotpipe.fromchild.read()
    if '-o' in sys.argv:
        output = open(sys.argv[sys.argv.index('-o') + 1], 'w').write(data)
    else:
        print data
        
