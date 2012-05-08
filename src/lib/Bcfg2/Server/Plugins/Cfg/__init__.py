"""This module implements a config file repository."""

import re
import os
import sys
import stat
import pkgutil
import logging
import binascii
import lxml.etree
import Bcfg2.Server.Plugin
from Bcfg2.Bcfg2Py3k import u_str

logger = logging.getLogger('Bcfg2.Plugins.Cfg')

PROCESSORS = None

class CfgBaseFileMatcher(Bcfg2.Server.Plugin.SpecificData):
    __extensions__ = []
    __ignore__ = []

    def __init__(self, fname, spec, encoding):
        Bcfg2.Server.Plugin.SpecificData.__init__(self, fname, spec, encoding)
        self.encoding = encoding
        self.regex = self.__class__.get_regex(fname)

    @classmethod
    def get_regex(cls, fname, extensions=None):
        if extensions is None:
            extensions = cls.__extensions__

        base_re = '^(?P<basename>%s)(|\\.H_(?P<hostname>\S+?)|.G(?P<prio>\d+)_(?P<group>\S+?))' % re.escape(fname)
        if extensions:
            base_re += '\\.(?P<extension>%s)' % '|'.join(extensions)
        base_re += '$'
        return re.compile(base_re)
    
    @classmethod
    def handles(cls, basename, event):
        return (event.filename.startswith(os.path.basename(basename)) and
                cls.get_regex(os.path.basename(basename)).match(event.filename))

    @classmethod
    def ignore(cls, basename, event):
        return (cls.__ignore__ and
                event.filename.startswith(os.path.basename(basename)) and
                cls.get_regex(os.path.basename(basename),
                              extensions=cls.__ignore__).match(event.filename))
        

    def __str__(self):
        return "%s(%s)" % (self.__class__.__name__, self.name)

    def match(self, fname):
        return self.regex.match(fname)


class CfgGenerator(CfgBaseFileMatcher):
    def get_data(self, entry, metadata):
        return self.data


class CfgFilter(CfgBaseFileMatcher):
    def modify_data(self, entry, metadata, data):
        raise NotImplementedError


class CfgInfo(Bcfg2.Server.Plugin.SpecificData):
    names = []
    regex = re.compile('^$')

    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)

    @classmethod
    def handles(cls, basename, event):
        return event.filename in cls.names or cls.regex.match(event.filename)

    @classmethod
    def ignore(cls, basename, event):
        return False

    def bind_info_to_entry(self, entry, metadata):
        raise NotImplementedError

    def _set_info(self, entry, info):
        for key, value in list(info.items()):
            entry.attrib.__setitem__(key, value)
    
    def __str__(self):
        return "%s(%s)" % (self.__class__.__name__, self.name)


class CfgDefaultInfo(CfgInfo):
    def __init__(self, defaults):
        self.name = ''
        self.defaults = defaults

    def handles(self, event):
        return False

    def bind_info_to_entry(self, entry, metadata):
        self._set_info(entry, self.defaults)


class CfgEntrySet(Bcfg2.Server.Plugin.EntrySet):
    def __init__(self, basename, path, entry_type, encoding):
        Bcfg2.Server.Plugin.EntrySet.__init__(self, basename, path,
                                              entry_type, encoding)
        self.specific = None
        self.default_info = CfgDefaultInfo(self.metadata)
        self.load_processors()

    def load_processors(self):
        """ load Cfg file processors.  this must be done at run-time,
        not at compile-time, or we get a circular import and things
        don't work.  but finding the right way to do this at runtime
        was ... problematic. so here it is, writing to a global
        variable.  Sorry 'bout that. """
        global PROCESSORS
        if PROCESSORS is None:
            PROCESSORS = []
            for submodule in pkgutil.walk_packages(path=__path__):
                module = getattr(__import__("%s.%s" %
                                            (__name__,
                                             submodule[1])).Server.Plugins.Cfg,
                                 submodule[1])
                proc = getattr(module, submodule[1])
                if set(proc.__mro__).intersection([CfgInfo, CfgFilter,
                                                   CfgGenerator]):
                    PROCESSORS.append(proc)

    def handle_event(self, event):
        action = event.code2str()
        
        for proc in PROCESSORS:
            if proc.handles(self.path, event):
                self.debug_log("%s handling %s event on %s" %
                               (proc.__name__, action, event.filename))
                if action in ['exists', 'created']:
                    self.entry_init(event, proc)
                elif event.filename not in self.entries:
                    logger.warning("Got %s event for unknown file %s" %
                                   (action, event.filename))
                    if action == 'changed':
                        # received a bogus changed event; warn, but
                        # treat it like a created event
                        self.entry_init(event, proc)
                elif action == 'changed':
                    self.entries[event.filename].handle_event(event)
                elif action == 'deleted':
                    del self.entries[event.filename]
                return
            elif proc.ignore(self.path, event):
                return

        logger.error("Could not process filename %s; ignoring" %
                     event.filename)

    def entry_init(self, event, proc):
        if CfgBaseFileMatcher in proc.__mro__:
            Bcfg2.Server.Plugin.EntrySet.entry_init(
                self, event, entry_type=proc,
                specific=proc.get_regex(os.path.basename(self.path)))
        else:
            if event.filename in self.entries:
                logger.warn("Got duplicate add for %s" % event.filename)
            else:
                fpath = os.path.join(self.path, event.filename)
                self.entries[event.filename] = proc(fpath)
            self.entries[event.filename].handle_event(event)

    def bind_entry(self, entry, metadata):
        info_handlers = []
        generators = []
        filters = []
        for ent in self.entries.values():
            if (hasattr(ent, 'specific') and
                not ent.specific.matches(metadata)):
                continue
            if isinstance(ent, CfgInfo):
                info_handlers.append(ent)
            elif isinstance(ent, CfgGenerator):
                generators.append(ent)
            elif isinstance(ent, CfgFilter):
                filters.append(ent)

        self.default_info.bind_info_to_entry(entry, metadata)
        if len(info_handlers) > 1:
            logger.error("More than one info supplier found for %s: %s" %
                         (self.name, info_handlers))
        if len(info_handlers):
            info_handlers[0].bind_info_to_entry(entry, metadata)
        if entry.tag == 'Path':
            entry.set('type', 'file')

        generator = self.best_matching(metadata, generators)
        if entry.get('perms').lower() == 'inherit':
            # use on-disk permissions
            fname = os.path.join(self.path, generator.name)
            entry.set('perms',
                      str(oct(stat.S_IMODE(os.stat(fname).st_mode))))
        try:
            data = generator.get_data(entry, metadata)
        except:
            msg = "Cfg: exception rendering %s with %s: %s" % \
                (entry.get("name"), generator, sys.exc_info()[1])
            logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)

        for fltr in filters:
            data = fltr.modify_data(entry, metadata, data)

        if entry.get('encoding') == 'base64':
            data = binascii.b2a_base64(data)
        else:
            try:
                data = u_str(data, self.encoding)
            except UnicodeDecodeError:
                msg = "Failed to decode %s: %s" % (entry.get('name'),
                                                   sys.exc_info()[1])
                logger.error(msg)
                logger.error("Please verify you are using the proper encoding.")
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
            except ValueError:
                msg = "Error in specification for %s: %s" % (entry.get('name'),
                                                             sys.exc_info()[1])
                logger.error(msg)
                logger.error("You need to specify base64 encoding for %s." %
                             entry.get('name'))
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)

        if data:
            entry.text = data
        else:
            entry.set('empty', 'true')

    def list_accept_choices(self, entry, metadata):
        '''return a list of candidate pull locations'''
        generators = [ent for ent in list(self.entries.values())
                      if (isinstance(ent, CfgGenerator) and
                          ent.specific.matches(metadata))]
        if not matching:
            msg = "No base file found for %s" % entry.get('name')
            logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
        
        rv = []
        try:
            best = self.best_matching(metadata, generators)
            rv.append(best.specific)
        except:
            pass

        if not rv or not rv[0].hostname:
            rv.append(Bcfg2.Server.Plugin.Specificity(hostname=metadata.hostname))
        return rv

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
                msg = "Cfg: Unable to pull data for genshi types"
                logger.error(msg)
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
            elif os.path.exists("%s.cheetah" % name):
                msg = "Cfg: Unable to pull data for cheetah types"
                logger.error(msg)
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
            try:
                etext = new_entry['text'].encode(self.encoding)
            except:
                msg = "Cfg: Cannot encode content of %s as %s" % (name,
                                                                  self.encoding)
                logger.error(msg)
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
            open(name, 'w').write(etext)
            self.debug_log("Wrote file %s" % name, flag=log)
        badattr = [attr for attr in ['owner', 'group', 'perms']
                   if attr in new_entry]
        if badattr:
            # check for info files and inform user of their removal
            if os.path.exists(self.path + "/:info"):
                logger.info("Removing :info file and replacing with "
                                 "info.xml")
                os.remove(self.path + "/:info")
            if os.path.exists(self.path + "/info"):
                logger.info("Removing info file and replacing with "
                                 "info.xml")
                os.remove(self.path + "/info")
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
            self.debug_log("Wrote file %s" % (self.path + "/info.xml"),
                           flag=log)


class Cfg(Bcfg2.Server.Plugin.GroupSpool,
          Bcfg2.Server.Plugin.PullTarget):
    """This generator in the configuration file repository for Bcfg2."""
    name = 'Cfg'
    __author__ = 'bcfg-dev@mcs.anl.gov'
    es_cls = CfgEntrySet
    es_child_cls = Bcfg2.Server.Plugin.SpecificData

    def AcceptChoices(self, entry, metadata):
        return self.entries[entry.get('name')].list_accept_choices(entry,
                                                                   metadata)

    def AcceptPullData(self, specific, new_entry, log):
        return self.entries[new_entry.get('name')].write_update(specific,
                                                                new_entry,
                                                                log)
