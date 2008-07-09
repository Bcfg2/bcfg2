import lxml.etree
import fcntl
import Bcfg2.Server.Admin

class Client(Bcfg2.Server.Admin.Mode):
    __shorthelp__ = 'bcfg2-admin client add <client> attr1=val1 attr2=val2\nbcfg2-admin client del <client>'
    __longhelp__ = __shorthelp__ + '\n\tCreate or delete client entries'
    def __init__(self, configfile):
        Bcfg2.Server.Admin.Mode.__init__(self, configfile)
        try:
            self.bcore = Bcfg2.Server.Core.Core(self.get_repo_path(),
                                                [], ['Metadata'],
                                                'foo', False, 'UTF-8')
        except Bcfg2.Server.Core.CoreInitError, msg:
            self.errExit("Core load failed because %s" % msg)
        [self.bcore.fam.Service() for _ in range(5)]
        while self.bcore.fam.Service():
            pass
        self.tree = lxml.etree.parse(self.get_repo_path() + "/Metadata/clients.xml")
        self.root = self.tree.getroot()

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        if len(args) == 0:
            self.errExit("Client mode requires at least one argument: <add> or <delete>")
        if "-h" in args:
            print "Usage: "
            print self.__shorthelp__
            raise SystemExit(1)
	if args[0] == 'add':
            attr_d = {}
            for i in args[2:]:
                attr, val = i.split('=', 1)
                if attr not in ['profile', 'uuid', 'password', 'address',
                                'secure', 'location']:
                    print "Attribute %s unknown" % attr
                    raise SystemExit(1)
                attr_d[attr] = val
            self.add_client(args[1], attr_d)
        elif args[0] in ['delete', 'remove', 'del', 'rm']:
            self.del_client(args[1])
        else:
            print "No command specified"
            raise SystemExit(1)
        client_tree = open(self.get_repo_path() + "/Metadata/clients.xml","w")
        fd = client_tree.fileno()
        while True:
            try:
                fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                continue
            else:
                break
        self.tree.write(client_tree)        
        fcntl.lockf(fd, fcntl.LOCK_UN)
        client_tree.close()
    
    def add_client(self, client, attrs):
        '''add a new client'''
        element = lxml.etree.Element("Client", name=client)
        for key, val in attrs.iteritems():
            element.set(key, val)
        node = self.search_client(client)
        if node != None:
            print "Client \"%s\" already exists" % (client)
            raise SystemExit(1)
        self.root.append(element)

    def del_client(self, client):
        '''delete an existing client'''
        node = self.search_client(client)
        if node == None:
            print "Client \"%s\" not found" % (client)
            raise SystemExit(1)
        self.root.remove(node)

    def search_client(self, client):
        '''find a client'''
        for node in self.root:
            if node.attrib["name"] == client:
                return node
            for child in node:
                if child.tag == "Alias" and child.attrib["name"] == client:
                    return node                   
        return None
