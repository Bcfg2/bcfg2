import copy
import lxml.etree

import Bcfg2.Server.Plugin


class PropertyFile(Bcfg2.Server.Plugin.StructFile):
    """Class for properties files."""
    def Index(self):
        """Build internal data structures."""
        if type(self.data) is not lxml.etree._Element:
            try:
                self.data = lxml.etree.XML(self.data)
            except lxml.etree.XMLSyntaxError:
                Bcfg2.Server.Plugin.logger.error("Failed to parse %s" %
                                                 self.name)

        self.fragments = {}
        work = {lambda x: True: self.data.getchildren()}
        while work:
            (predicate, worklist) = work.popitem()
            self.fragments[predicate] = \
                                      [item for item in worklist
                                       if (item.tag != 'Group' and
                                           item.tag != 'Client' and
                                           not isinstance(item,
                                                          lxml.etree._Comment))]
            for item in worklist:
                cmd = None
                if item.tag == 'Group':
                    if item.get('negate', 'false').lower() == 'true':
                        cmd = "lambda x:'%s' not in x.groups and predicate(x)"
                    else:
                        cmd = "lambda x:'%s' in x.groups and predicate(x)"
                elif item.tag == 'Client':
                    if item.get('negate', 'false').lower() == 'true':
                        cmd = "lambda x:x.hostname != '%s' and predicate(x)"
                    else:
                        cmd = "lambda x:x.hostname == '%s' and predicate(x)"
                # else, ignore item
                if cmd is not None:
                    newpred = eval(cmd % item.get('name'),
                                   {'predicate':predicate})
                    work[newpred] = item.getchildren()



class PropDirectoryBacked(Bcfg2.Server.Plugin.DirectoryBacked):
    __child__ = PropertyFile


class Properties(Bcfg2.Server.Plugin.Plugin,
                 Bcfg2.Server.Plugin.Connector):
    """
       The properties plugin maps property
       files into client metadata instances.
    """
    name = 'Properties'
    version = '$Revision$'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        try:
            self.store = PropDirectoryBacked(self.data, core.fam)
        except OSError:
            e = sys.exc_info()[1]
            Bcfg2.Server.Plugin.logger.error("Error while creating Properties "
                                             "store: %s %s" % (e.strerror, e.filename))
            raise Bcfg2.Server.Plugin.PluginInitError

    def get_additional_data(self, _):
        return copy.deepcopy(self.store.entries)
