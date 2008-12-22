import getopt
import Bcfg2.Server.Admin

class Pull(Bcfg2.Server.Admin.MetadataCore):
    '''
    Pull mode retrieves entries from clients and
    integrates the information into the repository
    '''
    __shorthelp__ = ("Integrate configuration information "
                     "from clients into the server repository")
    __longhelp__ = (__shorthelp__ + "\n\nbcfg2-admin pull [-v] [-f][-I]"
                                    "<client> <entry type> <entry name>")
    __usage__ = ("bcfg2-admin pull [options] <client> <entry type> "
                 "<entry name>\n\n"
                 "     %-25s%s\n"
                 "     %-25s%s\n"
                 "     %-25s%s\n" %
                ("-v",
                 "be verbose",
                 "-f",
                 "force",
                 "-I",
                 "interactive"))
    allowed = ['Metadata', 'BB', "DBStats", "Statistics", "Cfg", "SSHbase"]

    def __init__(self, configfile):
        Bcfg2.Server.Admin.MetadataCore.__init__(self, configfile,
                                                 self.__usage__)
        self.stats = self.bcore.stats
        self.log = False
        self.mode = 'interactive'
        
    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        try:
            opts, gargs = getopt.getopt(args, 'vfI')
        except:
            print self.__shorthelp__
            raise SystemExit(1)
        for opt in opts:
            if opt[0] == '-v':
                self.log = True
            elif opt[0] == '-f':
                self.mode = 'force'
            elif opt[0] == '-I':
                self.mode == 'interactive'
        self.PullEntry(gargs[0], gargs[1], gargs[2])

    def BuildNewEntry(self, client, etype, ename):
        '''construct a new full entry for given client/entry from statistics'''
        new_entry = {'type':etype, 'name':ename}
        try:
            (owner, group, perms, contents) = \
                    self.stats.GetCurrentEntry(client, etype, ename)
        except Bcfg2.Server.Plugin.PluginExecutionError:
            print "Statistics plugin failure; could not fetch current state"
            raise SystemExit(1)

        data = {'owner':owner, 'group':group, 'perms':perms, 'text':contents}
        for k, v in data.iteritems():
            if v:
                new_entry[k] = v
        #print new_entry
        return new_entry

    def Choose(self, choices):
        '''Determine where to put pull data'''
        if self.mode == 'interactive':
            for choice in choices:
                print "Plugin returned choice:"
                if id(choice) == id(choices[0]):
                    print "(current entry)", 
                if choice.all:
                    print " => global entry"
                elif choice.group:
                    print (" => group entry: %s (prio %d)" %
                           (choice.group, choice.prio))
                else:
                    print " => host entry: %s" % (choice.hostname)
                if raw_input("Use this entry? [yN]: ") in ['y', 'Y']:
                    return choice
            return False
        else:
            # mode == 'force'
            if not choices:
                return False
            return choices[0]

    def PullEntry(self, client, etype, ename):
        '''Make currently recorded client state correct for entry'''
        new_entry = self.BuildNewEntry(client, etype, ename)

        meta = self.bcore.metadata.get_metadata(client)
        # find appropriate plugin in bcore
        glist = [gen for gen in self.bcore.generators if
                 ename in gen.Entries.get(etype, {})]
        if len(glist) != 1:
            self.errExit("Got wrong numbers of matching generators for entry:" \
                         + "%s" % ([g.__name__ for g in glist]))
        plugin = glist[0]
        try:
            choices = plugin.AcceptChoices(new_entry, meta)
            specific = self.Choose(choices)
            if specific:
                plugin.AcceptPullData(specific, new_entry, self.log)
        except Bcfg2.Server.Plugin.PluginExecutionError:
            self.errExit("Configuration upload not supported by plugin %s" \
                         % (plugin.__name__))
        # FIXME svn commit if running under svn
