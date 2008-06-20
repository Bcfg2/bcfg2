
import getopt, popen2, lxml.etree
import Bcfg2.Server.Admin

class Viz(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = '''bcfg2-admin viz [--includehosts] [--includebundles] [--includekey] [-o output.png] [--raw]'''
    __longhelp__ = __shorthelp__ + '\n\tProduce graphviz diagrams of metadata structures'

    colors = ['steelblue1', 'chartreuse', 'gold', 'magenta',
              'indianred1', 'limegreen', 'orange1', 'lightblue2',
              'green1', 'blue1', 'yellow1', 'darkturquoise', 'gray66']

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        # First get options to the 'viz' subcommand
        try:
            opts, args = getopt.getopt(args, 'rhbko:',
                                       ['raw', 'includehosts', 'includebundles',
                                        'includekey', 'outfile='])
        except getopt.GetoptError, msg:
            print msg
            raise SystemExit(1)

        rset = False
        hset = False
        bset = False
        kset = False
        outputfile = False
        for opt, arg in opts:
            if opt in ("-r", "--raw"):
                rset = True
            elif opt in ("-h", "--includehosts"):
                hset = True
            elif opt in ("-b", "--includebundles"):
                bset = True
            elif opt in ("-k", "--includekey"):
                kset = True
            elif opt in ("-o", "--outfile"):
                outputfile = arg

        data = self.Visualize(self.get_repo_path(), rset, hset, bset,
                              kset, outputfile)
        print data

    def Visualize(self, repopath, raw=False, hosts=False,
                  bundles=False, key=False, output=False):
        '''Build visualization of groups file'''
        groupdata = lxml.etree.parse(repopath + '/Metadata/groups.xml')
        groupdata.xinclude()
        groups = groupdata.getroot()
        if raw:
            cmd = "dd bs=4M"
            if output:
                cmd += " of=%s" % output
        else:
            cmd = "dot -Tpng"
            if output:
                cmd += " -o %s" % output
        dotpipe = popen2.Popen4(cmd)
        categories = {'default':'grey83'}
        instances = {}
        egroups = groups.findall("Group") + groups.findall('.//Groups/Group')
        for group in egroups:
            if not categories.has_key(group.get('category')):
                categories[group.get('category')] = self.colors.pop()
            group.set('color', categories[group.get('category')])
        if None in categories:
            del categories[None]
        
        try:
            dotpipe.tochild.write("digraph groups {\n")
        except:
            print "write to dot process failed. Is graphviz installed?"
            raise SystemExit(1)
        dotpipe.tochild.write('\trankdir="LR";\n')

        if hosts:
            clients = lxml.etree.parse(repopath + \
                                       '/Metadata/clients.xml').getroot()
            for client in clients.findall('Client'):
                if instances.has_key(client.get('profile')):
                    instances[client.get('profile')].append(client.get('name'))
                else:
                    instances[client.get('profile')] = [client.get('name')]
            for profile, clist in instances.iteritems():
                clist.sort()
                dotpipe.tochild.write(
                    '''\t"%s-instances" [ label="%s", shape="record" ];\n''' \
                    % (profile, '|'.join(clist)))
                dotpipe.tochild.write('''\t"%s-instances" -> "group-%s";\n''' \
                                      % (profile, profile))

        if bundles:
            bundles = []
            [bundles.append(bund.get('name')) \
             for bund in groups.findall('.//Bundle')
             if bund.get('name') not in bundles]
            bundles.sort()
            for bundle in bundles:
                dotpipe.tochild.write(
                    '''\t"bundle-%s" [ label="%s", shape="septagon"];\n''' \
                    % (bundle, bundle))
        gseen = []
        for group in egroups:
            if group.get('profile', 'false') == 'true':
                style = "filled, bold"
            else:
                style = "filled"
            gseen.append(group.get('name'))
            dotpipe.tochild.write(
                '\t"group-%s" [label="%s", style="%s", fillcolor=%s];\n' %
                (group.get('name'), group.get('name'), style, group.get('color')))
            if bundles:
                for bundle in group.findall('Bundle'):
                    dotpipe.tochild.write('\t"group-%s" -> "bundle-%s";\n' %
                                          (group.get('name'), bundle.get('name')))
        
        gfmt = '\t"group-%s" [label="%s", style="filled", fillcolor="grey83"];\n' 
        for group in egroups:
            for parent in group.findall('Group'):
                if parent.get('name') not in gseen:
                    dotpipe.tochild.write(gfmt % (parent.get('name'),
                                                  parent.get('name')))
                    gseen.append(parent.get("name"))
                dotpipe.tochild.write('\t"group-%s" -> "group-%s" ;\n' %
                                      (group.get('name'), parent.get('name')))

        if key:
            dotpipe.tochild.write("\tsubgraph cluster_key {\n")
            dotpipe.tochild.write('''\tstyle="filled";\n''')
            dotpipe.tochild.write('''\tcolor="lightblue";\n''')
            dotpipe.tochild.write('''\tBundle [ shape="septagon" ];\n''')
            dotpipe.tochild.write('''\tGroup [shape="ellipse"];\n''')
            dotpipe.tochild.write('''\tProfile [style="bold", shape="ellipse"];\n''')
            dotpipe.tochild.write('''\tHblock [label="Host1|Host2|Host3", shape="record"];\n''')
            for category in categories:
                dotpipe.tochild.write(
                    '''\t"''' + category + '''" [label="''' + category + \
                    '''", shape="record", style="filled", fillcolor=''' + \
                    categories[category] + '''];\n''')
            dotpipe.tochild.write('''\tlabel="Key";\n''')
            dotpipe.tochild.write("\t}\n")
        dotpipe.tochild.write("}\n")
        dotpipe.tochild.close()
        return dotpipe.fromchild.read()
