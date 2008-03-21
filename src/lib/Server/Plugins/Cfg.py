'''This module implements a config file repository'''
__revision__ = '$Revision$'

import binascii, difflib, logging, os, re, tempfile, \
       xml.sax.saxutils, Bcfg2.Server.Plugin, lxml.etree

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

class CfgMatcher:
    def __init__(self, fname):
        name = re.escape(fname)
        self.basefile_reg = re.compile('^%s(|\\.H_(?P<hostname>\S+)|.G(?P<prio>\d+)_(?P<group>\S+))$' % name)
        self.delta_reg = re.compile('^%s(|\\.H_(?P<hostname>\S+)|\\.G(?P<prio>\d+)_(?P<group>\S+))\\.(?P<delta>(cat|diff))$' % fname)
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
                
    def bind_entry(self, entry, metadata):
        matching = [ent for ent in self.entries.values() if \
                    ent.specific.matches(metadata)]
        if [ent for ent in matching if ent.specific.delta]:
            self.bind_info_to_entry(entry, metadata)
            matching.sort(self.sort_by_specific)
            base = min([matching.index(ent) for ent in matching
                        if not ent.specific.delta])
            used = matching[:base+1]
            used.reverse()
            # used is now [base, delta1, delta2]            
            basefile = used.pop()
            data = basefile.data
            for delta in used:
                data = process_delta(data, delta)
            if entry.get('encoding') == 'base64':
                entry.text = binascii.b2a_base64(data)
            else:
                entry.text = data            
        else:
            Bcfg2.Server.Plugin.EntrySet.bind_entry(self, entry, metadata)

class Cfg(Bcfg2.Server.Plugin.GroupSpool):
    '''This generator in the configuration file repository for bcfg2'''
    __name__ = 'Cfg'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    use_props = False
    es_cls = CfgEntrySet
    es_child_cls = CfgEntry

    def AcceptEntry(self, meta, _, entry_name, diff, fulldata, metadata_updates={}):
        '''per-plugin bcfg2-admin pull support'''
        if metadata_updates:
            if hasattr(self.Entries['ConfigFile'][entry_name], 'infoxml'):
                print "InfoXML support not yet implemented"
            elif raw_input("Should metadata updates apply to all hosts? (n/Y) ") in ['Y', 'y']:
                self.entries[entry_name].metadata.update(metadata_updates)
                infofile = open(self.entries[entry_name].repopath + '/:info', 'w')
                for x in self.entries[entry_name].metadata.iteritems():
                    infofile.write("%s: %s\n" % x)
                infofile.close()
        if not diff and not fulldata:
            raise SystemExit, 0
                
        hsq = "Found host-specific file %s; Should it be updated (n/Y): "
        repo_vers = lxml.etree.Element('ConfigFile', name=entry_name)
        self.Entries['ConfigFile'][entry_name](repo_vers, meta)
        repo_curr = repo_vers.text
        # find the file fragment
        basefile = [frag for frag in \
                    self.entries[entry_name].fragments \
                    if frag.applies(meta)][-1]
        gsq = "Should this change apply to all hosts effected by file %s? (N/y): " % (basefile.name)
        if ".H_%s" % (meta.hostname) in basefile.name:
            answer = raw_input(hsq % basefile.name)
        else:
            answer = raw_input(gsq)
        
        if answer in ['Y', 'y']:
            print "writing file, %s" % basefile.name
            if fulldata:
                newdata = fulldata
            else:
                newdata = '\n'.join(difflib.restore(diff.split('\n'), 1))
            open(basefile.name, 'w').write(newdata)
            return

        if ".H_%s" % (meta.hostname) in basefile.name:
            raise SystemExit, 1
        # figure out host-specific filename
        reg = re.compile("(.*)\.G\d+.*")
        if reg.match(basefile.name):
            newname = reg.match(basefile.name).group(1) + ".H_%s" % (meta.hostname)
        else:
            newname = basefile.name + ".H_%s" % (meta.hostname)
        print "This file will be installed as file %s" % newname
        if raw_input("Should it be installed? (N/y): ") in ['Y', 'y']:
            print "writing file, %s" % newname
            if fulldata:
                newdata = fulldata
            else:
                newdata = '\n'.join(difflib.restore(diff.split('\n'), 1))
            open(newname, 'w').write(newdata)
