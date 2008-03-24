'''This module implements a config file repository'''
__revision__ = '$Revision$'

import binascii, logging, os, re, tempfile, Bcfg2.Server.Plugin

logger = logging.getLogger('Bcfg2.Plugins.Cfg')

def process_delta(data, delta):
    if not delta.specific.delta:
        return data
    if delta.specific.delta == 'cat':
        datalines = data.split('\n')
        for line in delta.data.split('\n'):
            if not line:
                continue
            if line[0] == '+':
                datalines.append(line[1:])
            elif line[0] == '-':
                if line[1:] in datalines:
                    datalines.remove(line[1:])
        return "\n".join(datalines) + "\n"
    elif delta.op == 'diff':
        basefile = open(tempfile.mktemp(), 'w')
        basefile.write(data)
        basefile.close()
        dfile = open(tempfile.mktemp(), 'w')
        dfile.write(delta.data)
        dfile.close()
        ret = os.system("patch -uf %s < %s > /dev/null 2>&1" \
                        % (basefile.name, dfile.name))
        output = open(basefile.name, 'r').read()
        [os.unlink(fname) for fname in [basefile.name, dfile.name]]
        if ret >> 8 != 0:
            raise Bcfg2.Server.Plugin.PluginExecutionError, ('delta', delta)
        return output

class CfgEntry(object):
    def __init__(self, name, _, specific):
        self.name = name
        self.specific = specific

    def handle_event(self, event):
        if event.code2str() == 'deleted':
            return
        try:
            self.data = open(self.name).read()
            self.usable = True
        except:
            logger.error("Failed to read file %s" % self.name)

    def bind_entry(self, entry, _):
        if entry.get('encoding') == 'base64':
            entry.text = binascii.b2a_base64(self.data)
        else:
            entry.text = self.data
        if not entry.text:
            entry.set('empty', 'true')

class CfgMatcher:
    def __init__(self, fname):
        name = re.escape(fname)
        self.basefile_reg = re.compile('^(?P<basename>%s)(|\\.H_(?P<hostname>\S+)|.G(?P<prio>\d+)_(?P<group>\S+))$' % name)
        self.delta_reg = re.compile('^(?P<basename>%s)(|\\.H_(?P<hostname>\S+)|\\.G(?P<prio>\d+)_(?P<group>\S+))\\.(?P<delta>(cat|diff))$' % fname)
        self.cat_count = fname.count(".cat")
        self.diff_count = fname.count(".diff")

    def match(self, fname):
        if fname.count(".cat") > self.cat_count \
               or fname.count('.diff') > self.diff_count:
            return self.delta_reg.match(fname)
        return self.basefile_reg.match(fname)

class CfgEntrySet(Bcfg2.Server.Plugin.EntrySet):
    def __init__(self, basename, path, props, entry_type):
        Bcfg2.Server.Plugin.EntrySet.__init__(self, basename, path, props, entry_type)
        self.specific = CfgMatcher(path.split('/')[-1])

    def sort_by_specific(self, one, other):
        return cmp(one.specific, other.specific)

    def get_pertinent_entries(self, metadata):
        '''return a list of all entries pertinent to a client => [base, delta1, delta2]'''
        matching = [ent for ent in self.entries.values() if \
                    ent.specific.matches(metadata)]
        matching.sort(self.sort_by_specific)
        base = min([matching.index(ent) for ent in matching
                    if not ent.specific.delta])
        used = matching[:base+1]
        used.reverse()
        return used

    def bind_entry(self, entry, metadata):
        self.bind_info_to_entry(entry, metadata)
        used = self.get_pertinent_entries(metadata)
        basefile = used.pop()
        data = basefile.data
        for delta in used:
            data = process_delta(data, delta)
        if entry.get('encoding') == 'base64':
            entry.text = binascii.b2a_base64(data)
        else:
            entry.text = data            

    def list_accept_choices(self, metadata):
        '''return a list of candidate pull locations'''
        used = self.get_pertinent_entries(metadata)
        if len(used) > 1:
            return []
        return [used[0].specific]

    def build_filename(self, specific):
        bfname = self.path + '/' + self.path.split('/')[-1]
        if specific.all:
            return bfname
        elif specific.group:
            return "%s.G%d_%s" % (bfname, specific.group, specific.prio)
        elif specific.hostname:
            return "%s.H_%s" % (bfname, specific.hostname)

    def write_update(self, specific, new_entry, log):
        name = self.build_filename(specific)
        open(name, 'w').write(new_entry['text'])
        if log:
            logger.info("Wrote file %s" % name)
        badattr = [attr for attr in ['owner', 'group', 'perms'] if attr in new_entry]
        if badattr:
            if hasattr(self.entries[name.split('/')[-1]], 'infoxml'):
                print "InfoXML support not yet implemented"
                return
            metadata_updates = {}
            metadata_updates.update(self.metadata)
            for attr in badattr:
                metadata_updates[attr] = new_entry.get('attr')
            infofile = open(self.path + '/:info', 'w')
            for x in metadata_updates.iteritems():
                infofile.write("%s: %s\n" % x)
            infofile.close()
            if log:
                logger.info("Wrote file %s" % infofile.name)

class Cfg(Bcfg2.Server.Plugin.GroupSpool):
    '''This generator in the configuration file repository for bcfg2'''
    __name__ = 'Cfg'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    use_props = False
    es_cls = CfgEntrySet
    es_child_cls = CfgEntry

    def AcceptChoices(self, entry, metadata):
        return self.entries[entry.get('name')].list_accept_choices(metadata)

    def AcceptPullData(self, specific, new_entry, log):
        return self.entries[new_entry.get('name')].write_update(specific, new_entry, log)

