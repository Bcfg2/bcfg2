"""This module implements a config file repository."""
__revision__ = '$Revision$'

import binascii
import logging
import lxml
import operator
import os
import os.path
import re
import stat
import sys
import tempfile
from subprocess import Popen, PIPE
from Bcfg2.Bcfg2Py3k import u_str

import Bcfg2.Server.Plugin

try:
    import genshi.core
    import genshi.input
    from genshi.template import TemplateLoader, NewTextTemplate
    have_genshi = True
except:
    have_genshi = False

try:
    import Cheetah.Template
    import Cheetah.Parser
    have_cheetah = True
except:
    have_cheetah = False

logger = logging.getLogger('Bcfg2.Plugins.Cfg')


# snipped from TGenshi
def removecomment(stream):
    """A genshi filter that removes comments from the stream."""
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


def process_delta(data, delta):
    if not delta.specific.delta:
        return data
    if delta.specific.delta == 'cat':
        datalines = data.strip().split('\n')
        for line in delta.data.split('\n'):
            if not line:
                continue
            if line[0] == '+':
                datalines.append(line[1:])
            elif line[0] == '-':
                if line[1:] in datalines:
                    datalines.remove(line[1:])
        return "\n".join(datalines) + "\n"
    elif delta.specific.delta == 'diff':
        basehandle, basename = tempfile.mkstemp()
        basefile = open(basename, 'w')
        basefile.write(data)
        basefile.close()
        os.close(basehandle)
        
        cmd = ["patch", "-u", "-f", basefile.name]
        patch = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stderr = patch.communicate(input=delta.data)[1]
        ret = patch.wait()
        output = open(basefile.name, 'r').read()
        os.unlink(basefile.name)
        if ret >> 8 != 0:
            logger.error("Error applying diff %s: %s" % (delta.name, stderr))
            raise Bcfg2.Server.Plugin.PluginExecutionError('delta', delta)
        return output


class CfgMatcher:

    def __init__(self, fname):
        name = re.escape(fname)
        self.basefile_reg = re.compile('^(?P<basename>%s)(|\\.H_(?P<hostname>\S+?)|.G(?P<prio>\d+)_(?P<group>\S+?))((?P<genshi>\\.genshi)|(?P<cheetah>\\.cheetah))?$' % name)
        self.delta_reg = re.compile('^(?P<basename>%s)(|\\.H_(?P<hostname>\S+)|\\.G(?P<prio>\d+)_(?P<group>\S+))\\.(?P<delta>(cat|diff))$' % name)
        self.cat_count = fname.count(".cat")
        self.diff_count = fname.count(".diff")

    def match(self, fname):
        if fname.count(".cat") > self.cat_count \
               or fname.count('.diff') > self.diff_count:
            return self.delta_reg.match(fname)
        return self.basefile_reg.match(fname)


class CfgEntrySet(Bcfg2.Server.Plugin.EntrySet):

    def __init__(self, basename, path, entry_type, encoding):
        Bcfg2.Server.Plugin.EntrySet.__init__(self, basename, path,
                                              entry_type, encoding)
        self.specific = CfgMatcher(path.split('/')[-1])
        path = path

    def sort_by_specific(self, one, other):
        return cmp(one.specific, other.specific)

    def get_pertinent_entries(self, entry, metadata):
        """return a list of all entries pertinent
        to a client => [base, delta1, delta2]
        """
        matching = [ent for ent in list(self.entries.values()) if \
                    ent.specific.matches(metadata)]
        matching.sort(key=operator.attrgetter('specific'))
        # base entries which apply to a client
        # (e.g. foo, foo.G##_groupname, foo.H_hostname)
        base_files = [matching.index(m) for m in matching
                      if not m.specific.delta]
        if not base_files:
            logger.error("No base file found for %s" % entry.get('name'))
            raise Bcfg2.Server.Plugin.PluginExecutionError
        base = min(base_files)
        used = matching[:base + 1]
        used.reverse()
        return used

    def bind_entry(self, entry, metadata):
        self.bind_info_to_entry(entry, metadata)
        used = self.get_pertinent_entries(entry, metadata)
        basefile = used.pop(0)
        if entry.get('perms').lower() == 'inherit':
            # use on-disk permissions
            fname = "%s/%s" % (self.path, entry.get('name'))
            entry.set('perms',
                      str(oct(stat.S_IMODE(os.stat(fname).st_mode))))
        if entry.tag == 'Path':
            entry.set('type', 'file')
        if basefile.name.endswith(".genshi"):
            if not have_genshi:
                logger.error("Cfg: Genshi is not available")
                raise Bcfg2.Server.Plugin.PluginExecutionError
            try:
                template_cls = NewTextTemplate
                loader = TemplateLoader()
                template = loader.load(basefile.name, cls=template_cls,
                                       encoding=self.encoding)
                fname = entry.get('realname', entry.get('name'))
                stream = template.generate(name=fname,
                                           metadata=metadata,
                                           path=basefile.name).filter(removecomment)
                try:
                    data = stream.render('text', encoding=self.encoding,
                                         strip_whitespace=False)
                except TypeError:
                    data = stream.render('text', encoding=self.encoding)
                if data == '':
                    entry.set('empty', 'true')
            except Exception:
                e = sys.exc_info()[1]
                logger.error("Cfg: genshi exception: %s" % e)
                raise Bcfg2.Server.Plugin.PluginExecutionError
        elif basefile.name.endswith(".cheetah"):
            if not have_cheetah:
                logger.error("Cfg: Cheetah is not available")
                raise Bcfg2.Server.Plugin.PluginExecutionError
            try:
                fname = entry.get('realname', entry.get('name'))
                s = {'useStackFrames': False}
                template = Cheetah.Template.Template(open(basefile.name).read(),
                                                       compilerSettings=s)
                template.metadata = metadata
                template.path = fname
                template.source_path = basefile.name
                data = template.respond()
                if data == '':
                    entry.set('empty', 'true')
            except Exception:
                e = sys.exc_info()[1]
                logger.error("Cfg: cheetah exception: %s" % e)
                raise Bcfg2.Server.Plugin.PluginExecutionError
        else:
            data = basefile.data
            for delta in used:
                data = process_delta(data, delta)
        if entry.get('encoding') == 'base64':
            entry.text = binascii.b2a_base64(data)
        else:
            try:
                entry.text = u_str(data, self.encoding)
            except UnicodeDecodeError:
                e = sys.exc_info()[1]
                logger.error("Failed to decode %s: %s" % (entry.get('name'), e))
                logger.error("Please verify you are using the proper encoding.")
                raise Bcfg2.Server.Plugin.PluginExecutionError
            except ValueError:
                e = sys.exc_info()[1]
                logger.error("Error in specification for %s" % entry.get('name'))
                logger.error("%s" % e)
                logger.error("You need to specify base64 encoding for %s." %
                             entry.get('name'))
                raise Bcfg2.Server.Plugin.PluginExecutionError
        if entry.text in ['', None]:
            entry.set('empty', 'true')

    def list_accept_choices(self, entry, metadata):
        '''return a list of candidate pull locations'''
        used = self.get_pertinent_entries(entry, metadata)
        ret = []
        if used:
            ret.append(used[0].specific)
        if not ret[0].hostname:
            ret.append(Bcfg2.Server.Plugin.Specificity(hostname=metadata.hostname))
        return ret

    def build_filename(self, specific):
        bfname = self.path + '/' + self.path.split('/')[-1]
        if specific.all:
            return bfname
        elif specific.group:
            return "%s.G%02d_%s" % (bfname, specific.prio, specific.group)
        elif specific.hostname:
            return "%s.H_%s" % (bfname, specific.hostname)

    def write_update(self, specific, new_entry, log):
        if 'text' in new_entry:
            name = self.build_filename(specific)
            if os.path.exists("%s.genshi" % name):
                logger.error("Cfg: Unable to pull data for genshi types")
                raise Bcfg2.Server.Plugin.PluginExecutionError
            elif os.path.exists("%s.cheetah" % name):
                logger.error("Cfg: Unable to pull data for cheetah types")
                raise Bcfg2.Server.Plugin.PluginExecutionError
            try:
                etext = new_entry['text'].encode(self.encoding)
            except:
                logger.error("Cfg: Cannot encode content of %s as %s" % (name, self.encoding))
                raise Bcfg2.Server.Plugin.PluginExecutionError
            open(name, 'w').write(etext)
            if log:
                logger.info("Wrote file %s" % name)
        badattr = [attr for attr in ['owner', 'group', 'perms']
                   if attr in new_entry]
        if badattr:
            metadata_updates = {}
            metadata_updates.update(self.metadata)
            for attr in badattr:
                metadata_updates[attr] = new_entry.get(attr)
            infoxml = lxml.etree.Element('FileInfo')
            infotag = lxml.etree.SubElement(infoxml, 'Info')
            [infotag.attrib.__setitem__(attr, metadata_updates[attr]) \
                for attr in metadata_updates]
            ofile = open(self.path + "/info.xml", "w")
            ofile.write(lxml.etree.tostring(infoxml, pretty_print=True))
            ofile.close()
            if log:
                logger.info("Wrote file %s" % (self.path + "/info.xml"))


class Cfg(Bcfg2.Server.Plugin.GroupSpool,
          Bcfg2.Server.Plugin.PullTarget):
    """This generator in the configuration file repository for Bcfg2."""
    name = 'Cfg'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    es_cls = CfgEntrySet
    es_child_cls = Bcfg2.Server.Plugin.SpecificData

    def AcceptChoices(self, entry, metadata):
        return self.entries[entry.get('name')].list_accept_choices(entry, metadata)

    def AcceptPullData(self, specific, new_entry, log):
        return self.entries[new_entry.get('name')].write_update(specific,
                                                                new_entry,
                                                                log)
