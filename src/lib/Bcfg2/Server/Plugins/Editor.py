import Bcfg2.Server.Plugin
import re
import lxml.etree


def linesub(pattern, repl, filestring):
    """Substitutes instances of pattern with repl in filestring."""
    if filestring == None:
        filestring = ''
    output = list()
    fileread = filestring.split('\n')
    for line in fileread:
        output.append(re.sub(pattern, repl, filestring))
    return '\n'.join(output)


class EditDirectives(Bcfg2.Server.Plugin.SpecificData):
    """This object handles the editing directives."""
    def ProcessDirectives(self, input):
        """Processes a list of edit directives on input."""
        temp = input
        for directive in self.data.split('\n'):
            directive = directive.split(',')
            temp = linesub(directive[0], directive[1], temp)
        return temp


class EditEntrySet(Bcfg2.Server.Plugin.EntrySet):
    def __init__(self, basename, path, entry_type, encoding):
        self.ignore = re.compile("^(\.#.*|.*~|\\..*\\.(tmp|sw[px])|%s\.H_.*)$" % path.split('/')[-1])
        Bcfg2.Server.Plugin.EntrySet.__init__(self,
                                              basename,
                                              path,
                                              entry_type,
                                              encoding)
        self.inputs = dict()

    def bind_entry(self, entry, metadata):
        client = metadata.hostname
        filename = entry.get('name')
        permdata = {'owner': 'root',
                    'group': 'root',
                    'mode': '0644'}
        [entry.attrib.__setitem__(key, permdata[key]) for key in permdata]
        entry.text = self.entries['edits'].ProcessDirectives(self.get_client_data(client))
        if not entry.text:
            entry.set('empty', 'true')
        try:
            f = open('%s/%s.H_%s' % (self.path, filename.split('/')[-1], client), 'w')
            f.write(entry.text)
            f.close()
        except:
            pass

    def get_client_data(self, client):
        return self.inputs[client]


class Editor(Bcfg2.Server.Plugin.GroupSpool,
             Bcfg2.Server.Plugin.Probing):
    name = 'Editor'
    __author__ = 'bcfg2-dev@mcs.anl.gov'
    filename_pattern = 'edits'
    es_child_cls = EditDirectives
    es_cls = EditEntrySet

    def GetProbes(self, _):
        '''Return a set of probes for execution on client'''
        probelist = list()
        for name in list(self.entries.keys()):
            probe = lxml.etree.Element('probe')
            probe.set('name', name)
            probe.set('source', "Editor")
            probe.text = "cat %s" % name
            probelist.append(probe)
        return probelist

    def ReceiveData(self, client, datalist):
        for data in datalist:
            self.entries[data.get('name')].inputs[client.hostname] = data.text
