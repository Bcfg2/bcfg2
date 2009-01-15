
import logging, re
import SGenshi

pattern = '(.*/)?(\S+)\.xml(\.((H_(?P<hostname>\S+))|' 
pattern += '(G(?P<prio>\d+)_(?P<group>\S+))))?$'

matcher = re.compile(pattern)

logger = logging.getLogger('GBundler')

class GBundlerEntrySet(SGenshi.SGenshiEntrySet):
    def BuildStructures(self, metadata):
        '''Build SGenshi structures'''
        ret = []
        found = []
        build = []
        matching = self.get_matching(metadata)
        matching.sort(lambda x,y: cmp(x.specific, y.specific))
        for entry in matching[:]:
            rem = matcher.match(entry.name)
            bname = rem.group(2)
            if bname in metadata.bundles and bname not in found:
                found.append(bname)
                build.append(entry)

        for entry in build:
            try:
                ret.append(entry.get_xml_value(metadata))
            except genshi.template.TemplateError, terror:
                logger.error('Genshi template error: %s' % terror)
                logger.error("GBundler: Failed to template file %s" % entry.name)
        return ret

class GBundler(GBundlerEntrySet, SGenshi.SGenshi):
    name = 'GBundler'
    __version__ = '$Revision: $'
    
