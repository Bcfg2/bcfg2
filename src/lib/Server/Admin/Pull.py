
import binascii, lxml.etree, time
import Bcfg2.Server.Admin

class Pull(Bcfg2.Server.Admin.Mode):
    '''Pull mode retrieves entries from clients and integrates the information into the repository'''
    __shorthelp__ = 'bcfg2-admin pull <client> <entry type> <entry name>'
    __longhelp__ = __shorthelp__ + '\n\tIntegrate configuration information from clients into the server repository'
    def __init__(self):
        Bcfg2.Server.Admin.Mode.__init__(self)

    def __call__(self, args):
        Bcfg2.Server.Admin.Mode.__call__(self, args)
        self.PullEntry(args[0], args[1], args[2])

    def PullEntry(self, client, etype, ename):
        '''Make currently recorded client state correct for entry'''
        # FIXME Pull.py is _way_ too interactive
        sdata = self.load_stats(client)
        if sdata.xpath('.//Statistics[@state="dirty"]'):
            state = 'dirty'
        else:
            state = 'clean'
        # need to pull entry out of statistics
        sxpath = ".//Statistics[@state='%s']/Bad/ConfigFile[@name='%s']/../.." % (state, ename)
        sentries = sdata.xpath(sxpath)
        if not len(sentries):
            self.errExit("Found %d entries for %s:%s:%s" % \
                         (len(sentries), client, etype, ename))
        else:
            print "Found %d entries for %s:%s:%s" % \
                  (len(sentries), client, etype, ename)
        maxtime = max([time.strptime(stat.get('time')) for stat in sentries])
        print "Found entry from", time.strftime("%c", maxtime)
        statblock = [stat for stat in sentries \
                     if time.strptime(stat.get('time')) == maxtime]
        entry = statblock[0].xpath('.//Bad/ConfigFile[@name="%s"]' % ename)
        if not entry:
            self.errExit("Could not find state data for entry; rerun bcfg2 on client system")
        cfentry = entry[-1]

        badfields = [field for field in ['perms', 'owner', 'group'] \
                     if cfentry.get(field) != cfentry.get('current_' + field) and \
                     cfentry.get('current_' + field)]
        if badfields:
            m_updates = dict([(field, cfentry.get('current_' + field)) \
                              for field in badfields])
            print "got metadata_updates", m_updates
        else:
            m_updates = {}

        if 'current_bdiff' in cfentry.attrib:
            data = False
            diff = binascii.a2b_base64(cfentry.get('current_bdiff'))
        elif 'current_diff' in cfentry.attrib:
            data = False
            diff = cfentry.get('current_diff')
        elif 'current_bfile' in cfentry.attrib:
            data = binascii.a2b_base64(cfentry.get('current_bfile'))
            diff = False
        else:
            if not m_updates:
                self.errExit("having trouble processing entry. Entry is:\n" \
                             + lxml.etree.tostring(cfentry))
            else:
                data = False
                diff = False

        if diff:
            print "Located diff:\n %s" % diff
        elif data:
            print "Found full (binary) file data"
        if m_updates:
            print "Found metadata updates"

        if not diff and not data and not m_updates:
            self.errExit("Failed to locate diff or full data or metadata updates\nStatistics entry was:\n%s" % lxml.etree.tostring(cfentry))

        try:
            bcore = Bcfg2.Server.Core.Core({}, self.configfile)
        except Bcfg2.Server.Core.CoreInitError, msg:
            self.errExit("Core load failed because %s" % msg)
        [bcore.fam.Service() for _ in range(10)]
        while bcore.fam.Service():
            pass
        m = bcore.metadata.get_metadata(client)
        # find appropriate plugin in bcore
        glist = [gen for gen in bcore.generators if
                 gen.Entries.get(etype, {}).has_key(ename)]
        if len(glist) != 1:
            self.errExit("Got wrong numbers of matching generators for entry:" \
                         + "%s" % ([g.__name__ for g in glist]))
        plugin = glist[0]
        try:
            plugin.AcceptEntry(m, 'ConfigFile', ename, diff, data, m_updates)
        except Bcfg2.Server.Plugin.PluginExecutionError:
            self.errExit("Configuration upload not supported by plugin %s" \
                         % (plugin.__name__))
        # svn commit if running under svn
