
import binascii, difflib, getopt, lxml.etree, time, ConfigParser
import Bcfg2.Server.Admin

class Pull(Bcfg2.Server.Admin.Mode):
    '''Pull mode retrieves entries from clients and integrates the information into the repository'''
    __shorthelp__ = 'bcfg2-admin pull [-v] [-f] [-I] <client> <entry type> <entry name>'
    __longhelp__ = __shorthelp__ + '\n\tIntegrate configuration information from clients into the server repository'
    def __init__(self, configfile):
        Bcfg2.Server.Admin.Mode.__init__(self, configfile)
        cp = ConfigParser.ConfigParser()
        cp.read([configfile])
        self.repo = cp.get('server', 'repository')
        self.log = False
        self.mode = 'interactive'
        
    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        try:
            opts, gargs = getopt.getopt(args, 'vfI')
        except:
            print self.__shorthelp__
            raise SystemExit(0)
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
        sdata = self.load_stats(client)
        # no entries if state != dirty
        sxpath = ".//Statistics[@state='dirty']/Bad/ConfigFile[@name='%s']/../.." % \
                 (ename)
        sentries = sdata.xpath(sxpath)
        if not len(sentries):
            self.errExit("Found %d entries for %s:%s:%s" % \
                         (len(sentries), client, etype, ename))
        else:
            if self.log:
                print "Found %d entries for %s:%s:%s" % \
                      (len(sentries), client, etype, ename)
        maxtime = max([time.strptime(stat.get('time')) for stat in sentries])
        if self.log:
            print "Found entry from", time.strftime("%c", maxtime)
        statblock = [stat for stat in sentries \
                     if time.strptime(stat.get('time')) == maxtime]
        entry = statblock[0].xpath('.//Bad/ConfigFile[@name="%s"]' % ename)
        if not entry:
            self.errExit("Could not find state data for entry\n" \
                         "rerun bcfg2 on client system")
        cfentry = entry[-1]

        badfields = [field for field in ['perms', 'owner', 'group'] \
                     if cfentry.get(field) != cfentry.get('current_' + field) and \
                     cfentry.get('current_' + field)]
        if badfields:
            for field in badfields:
                new_entry[field] = cfentry.get('current_%s' % field)
        # now metadata updates are in place
        if 'current_bfile' in cfentry.attrib:
            new_entry['text'] = binascii.a2b_base64(cfentry.get('current_bfile'))
        elif 'current_bdiff' in cfentry.attrib:
            diff = binascii.a2b_base64(cfentry.get('current_bdiff'))
            new_entry['text'] = '\n'.join(difflib.restore(diff.split('\n'), 1))
        else:
            print "found no data::"
            print lxml.etree.tostring(cfentry, encoding='UTF-8', xml_declaration=True)
            raise SystemExit(1)
        return new_entry

    def Choose(self, choices):
        '''Determine where to put pull data'''
        if self.mode == 'interactive':
            # FIXME improve bcfg2-admin pull interactive mode to add new entries
            print "Plugin returned choice:"
            if choices[0].all:
                print " => global entry"
            elif choices[0].group:
                print " => group entry: %s (prio %d)" % (choices[0].group, choices[0].prio)
            else:
                print " => host entry: %s" % (choices[0].hostname)
            if raw_input("Use this entry? [yN]: ") in ['y', 'Y']:
                return choices[0]
            return False
        else:
            # mode == 'force'
            return choices[0]

    def PullEntry(self, client, etype, ename):
        '''Make currently recorded client state correct for entry'''
        new_entry = self.BuildNewEntry(client, etype, ename)

        try:
            bcore = Bcfg2.Server.Core.Core(self.repo, [], [],
                                           ['Cfg', 'SSHbase'], 'foo', False)
        except Bcfg2.Server.Core.CoreInitError, msg:
            self.errExit("Core load failed because %s" % msg)
        [bcore.fam.Service() for _ in range(5)]
        while bcore.fam.Service():
            pass
        meta = bcore.metadata.get_metadata(client)
        # find appropriate plugin in bcore
        glist = [gen for gen in bcore.generators if
                 gen.Entries.get(etype, {}).has_key(ename)]
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
