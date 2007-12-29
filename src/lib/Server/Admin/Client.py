import lxml.etree

import Bcfg2.Server.Admin

class Client(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = 'bcfg2-admin client add <client> attr1=val1 attr2=val2\nbcfg2-admin client del <client>'
    __longhelp__ = __shorthelp__ + '\n\tCreate or delete client entries'
    def __init__(self, configfile):
        Bcfg2.Server.Admin.Mode.__init__(self, configfile)
        self.tree = lxml.etree.parse(self.get_repo_path() + \
                                     '/Metadata/clients.xml')
        self.root = self.tree.getroot()
    
    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        repopath = self.get_repo_path()
        if args[0] == 'add':
            attr_d = {}
            for i in args[1:]:
                attr, val = i.split('=', 1)
                if attr not in ['profile', 'uuid', 'password', 'address',
                                'secure', 'location']:
                    print "Attribute %s unknown" % attr
                    raise SystemExit(1)
                attr_d[attr] = val
            self.AddClient(args[1], attr_d)
        elif args[0] in ['delete', 'remove', 'del', 'rm']:
            self.DelClient(args[1])
        else:
            print "No command specified"
            raise SystemExit(1)
        self.tree.write(repopath + '/Metadata/clients.xml')        
    
    def AddClient(self, client, attrs):
        '''add a new client'''
        # FIXME add a dup client check
        element = lxml.etree.Element("Client", name=client)
        for key, val in attrs.iteritems():
            element.set(key, val)
        self.root.append(element)

    def DelClient(self, client):
        '''delete an existing client'''
        # FIXME DelClient not implemented
        pass

