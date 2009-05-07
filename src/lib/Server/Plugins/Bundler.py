'''This provides bundle clauses with translation functionality'''
__revision__ = '$Revision$'

import copy, lxml.etree, Bcfg2.Server.Plugin, re

try:
    import Bcfg2.Server.Plugins.SGenshi
    import genshi.template
    have_genshi = True
except:
    have_genshi = False

class BundleFile(Bcfg2.Server.Plugin.StructFile):
    def get_xml_value(self, metadata):
        bundlename = self.name.split('/')[-1][:-4]
        bundle = lxml.etree.Element('Bundle', name=bundlename)
        [bundle.append(copy.deepcopy(item)) for item in self.Match(metadata)]
        return bundle

class Bundler(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.Structure,
              Bcfg2.Server.Plugin.XMLDirectoryBacked):
    '''The bundler creates dependent clauses based on the bundle/translation scheme from bcfg1'''
    name =  'Bundler'
    __version__ = '$Id$'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    patterns = re.compile('^(?P<name>.*)\.(xml|genshi)$')
    
    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Structure.__init__(self)
        self.encoding = core.encoding
        self.__child__ = self.template_dispatch
        try:
            Bcfg2.Server.Plugin.XMLDirectoryBacked.__init__(self, self.data, self.core.fam)
        except OSError:
            self.logger.error("Failed to load Bundle repository")
            raise Bcfg2.Server.Plugin.PluginInitError

    def template_dispatch(self, name):
        if name.endswith('.xml'):
            return BundleFile(name)
        elif name.endswith('.genshi'):
            if have_genshi:
                spec = Bcfg2.Server.Plugin.Specificity()
                return Bcfg2.Server.Plugins.SGenshi.SGenshiTemplateFile(name,
                                                                        spec,
                                                                        self.encoding)

    def BuildStructures(self, metadata):
        '''Build all structures for client (metadata)'''
        bundleset = []
        for bundlename in metadata.bundles:
            entries = [item for (key, item) in self.entries.iteritems() if \
                       self.patterns.match(key).group('name') == bundlename]
            if len(entries) == 0:
                continue
            elif len(entries) == 1:
                try:
                    bundleset.append(entries[0].get_xml_value(metadata))
                except genshi.template.TemplateError, t:
                    self.logger.error("Bundler: Failed to template genshi bundle %s" \
                                      % (bundlename))
                    self.logger.error(t)
                except:
                    self.logger.error("Bundler: Unexpected bundler error for %s" \
                                      % (bundlename), exc_info=1)
            else:
                self.logger.error("Got multiple matches for bundle %s" \
                                  % (bundlename))
        return bundleset

