"""This module implements a config file repository."""

import re
import os
import sys
import stat
import pkgutil
import logging
import binascii
import lxml.etree
import Bcfg2.Options
import Bcfg2.Server.Plugin
from Bcfg2.Bcfg2Py3k import u_str
import Bcfg2.Server.Lint

logger = logging.getLogger(__name__)

PROCESSORS = None
SETUP = None

class CfgBaseFileMatcher(Bcfg2.Server.Plugin.SpecificData):
    __basenames__ = []
    __extensions__ = []
    __ignore__ = []
    __specific__ = True

    def __init__(self, fname, spec, encoding):
        Bcfg2.Server.Plugin.SpecificData.__init__(self, fname, spec, encoding)
        self.encoding = encoding
        self.regex = self.__class__.get_regex(fname)

    @classmethod
    def get_regex(cls, fname=None, extensions=None):
        if extensions is None:
            extensions = cls.__extensions__
        if cls.__basenames__:
            fname = '|'.join(cls.__basenames__)

        components = ['^(?P<basename>%s)' % fname]
        if cls.__specific__:
            components.append('(|\\.H_(?P<hostname>\S+?)|.G(?P<prio>\d+)_(?P<group>\S+?))')
        if extensions:
            components.append('\\.(?P<extension>%s)' % '|'.join(extensions))
        components.append('$')
        return re.compile("".join(components))
    
    @classmethod
    def handles(cls, event, basename=None):
        if cls.__basenames__:
            basenames = cls.__basenames__
        else:
            basenames = [basename]

        # do simple non-regex matching first
        match = False
        for bname in basenames:
            if event.filename.startswith(os.path.basename(bname)):
                match = True
                break
        return (match and
                cls.get_regex(fname=os.path.basename(basename)).match(event.filename))

    @classmethod
    def ignore(cls, event, basename=None):
        if not cls.__ignore__:
            return False

        if cls.__basenames__:
            basenames = cls.__basenames__
        else:
            basenames = [basename]

        # do simple non-regex matching first
        match = False
        for bname in basenames:
            if event.filename.startswith(os.path.basename(bname)):
                match = True
                break
        return (match and
                cls.get_regex(fname=os.path.basename(basename),
                              extensions=cls.__ignore__).match(event.filename))
        

    def __str__(self):
        return "%s(%s)" % (self.__class__.__name__, self.name)

    def match(self, fname):
        return self.regex.match(fname)


class CfgGenerator(CfgBaseFileMatcher):
    """ CfgGenerators generate the initial content of a file """
    def get_data(self, entry, metadata):
        return self.data


class CfgFilter(CfgBaseFileMatcher):
    """ CfgFilters modify the initial content of a file after it's
    been generated """
    def modify_data(self, entry, metadata, data):
        raise NotImplementedError


class CfgInfo(CfgBaseFileMatcher):
    """ CfgInfos provide metadata (owner, group, paranoid, etc.) for a
    file entry """
    __specific__ = False

    def __init__(self, fname):
        CfgBaseFileMatcher.__init__(self, fname, None, None)

    def bind_info_to_entry(self, entry, metadata):
        raise NotImplementedError

    def _set_info(self, entry, info):
        for key, value in list(info.items()):
            if not key.startswith("__"):
                entry.attrib.__setitem__(key, value)


class CfgVerifier(CfgBaseFileMatcher):
    """ Verifiers validate entries """
    def verify_entry(self, entry, metadata, data):
        raise NotImplementedError


class CfgVerificationError(Exception):
    pass


class CfgDefaultInfo(CfgInfo):
    def __init__(self, defaults):
        CfgInfo.__init__(self, '')
        self.defaults = defaults

    def bind_info_to_entry(self, entry, metadata):
        self._set_info(entry, self.defaults)

DEFAULT_INFO = CfgDefaultInfo(Bcfg2.Server.Plugin.default_file_metadata)

class CfgEntrySet(Bcfg2.Server.Plugin.EntrySet):
    def __init__(self, basename, path, entry_type, encoding):
        Bcfg2.Server.Plugin.EntrySet.__init__(self, basename, path,
                                              entry_type, encoding)
        self.specific = None
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
            if hasattr(pkgutil, 'walk_packages'):
                submodules = pkgutil.walk_packages(path=__path__)
            else:
                #python 2.4
                import glob
                submodules = []
                for path in __path__:
                    for submodule in glob.glob("%s/*.py" % path):
                        mod = '.'.join(submodule.split("/")[-1].split('.')[:-1])
                        if mod != '__init__':
                            submodules.append((None, mod, True))

            for submodule in submodules:
                module = getattr(__import__("%s.%s" %
                                            (__name__,
                                             submodule[1])).Server.Plugins.Cfg,
                                 submodule[1])
                proc = getattr(module, submodule[1])
                if set(proc.__mro__).intersection([CfgInfo, CfgFilter,
                                                   CfgGenerator, CfgVerifier]):
                    PROCESSORS.append(proc)

    def handle_event(self, event):
        action = event.code2str()
        
        if event.filename not in self.entries:
            if action not in ['exists', 'created', 'changed']:
                # process a bogus changed event like a created
                return
                
            for proc in PROCESSORS:
                if proc.handles(event, basename=self.path):
                    if action == 'changed':
                        # warn about a bogus 'changed' event, but
                        # handle it like a 'created'
                        logger.warning("Got %s event for unknown file %s" %
                                       (action, event.filename))
                    self.debug_log("%s handling %s event on %s" %
                                   (proc.__name__, action, event.filename))
                    self.entry_init(event, proc)
                    return
                elif proc.ignore(event, basename=self.path):
                    return
        elif action == 'changed':
            self.entries[event.filename].handle_event(event)
            return
        elif action == 'deleted':
            del self.entries[event.filename]
            return

        logger.error("Could not process event %s for %s; ignoring" %
                     (action, event.filename))

    def entry_init(self, event, proc):
        if proc.__specific__:
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
        verifiers = []
        for ent in self.entries.values():
            if ent.__specific__ and not ent.specific.matches(metadata):
                continue
            if isinstance(ent, CfgInfo):
                info_handlers.append(ent)
            elif isinstance(ent, CfgGenerator):
                generators.append(ent)
            elif isinstance(ent, CfgFilter):
                filters.append(ent)
            elif isinstance(ent, CfgVerifier):
                verifiers.append(ent)

        DEFAULT_INFO.bind_info_to_entry(entry, metadata)
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

        if SETUP['validate']:
            # we can have multiple verifiers, but we only want to use the
            # best matching verifier of each class
            verifiers_by_class = dict()
            for verifier in verifiers:
                cls = verifier.__class__.__name__
                if cls not in verifiers_by_class:
                    verifiers_by_class[cls] = [verifier]
                else:
                    verifiers_by_class[cls].append(verifier)
            for verifiers in verifiers_by_class.values():
                verifier = self.best_matching(metadata, verifiers)
                try:
                    verifier.verify_entry(entry, metadata, data)
                except CfgVerificationError:
                    msg = "Data for %s for %s failed to verify: %s" % \
                        (entry.get('name'), metadata.hostname,
                         sys.exc_info()[1])
                    logger.error(msg)
                    raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
                
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
            except TypeError:
                # data is already unicode; newer versions of Cheetah
                # seem to return unicode
                pass

        if data:
            entry.text = data
        else:
            entry.set('empty', 'true')

    def list_accept_choices(self, entry, metadata):
        '''return a list of candidate pull locations'''
        generators = [ent for ent in list(self.entries.values())
                      if (isinstance(ent, CfgGenerator) and
                          ent.specific.matches(metadata))]
        if not generators:
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

    def __init__(self, core, datastore):
        global SETUP
        Bcfg2.Server.Plugin.GroupSpool.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.PullTarget.__init__(self)
        
        SETUP = core.setup
        if 'validate' not in SETUP:
            SETUP.add_option('validate', Bcfg2.Options.CFG_VALIDATION)
            SETUP.reparse()

    def AcceptChoices(self, entry, metadata):
        return self.entries[entry.get('name')].list_accept_choices(entry,
                                                                   metadata)

    def AcceptPullData(self, specific, new_entry, log):
        return self.entries[new_entry.get('name')].write_update(specific,
                                                                new_entry,
                                                                log)

class CfgLint(Bcfg2.Server.Lint.ServerPlugin):
    """ warn about usage of .cat and .diff files """

    def Run(self):
        for basename, entry in list(self.core.plugins['Cfg'].entries.items()):
            self.check_entry(basename, entry)


    @classmethod
    def Errors(cls):
        return {"cat-file-used":"warning",
                "diff-file-used":"warning"}

    def check_entry(self, basename, entry):
        cfg = self.core.plugins['Cfg']
        for basename, entry in list(cfg.entries.items()):
            for fname, processor in entry.entries.items():
                if self.HandlesFile(fname) and isinstance(processor, CfgFilter):
                    extension = fname.split(".")[-1]
                    self.LintError("%s-file-used" % extension,
                                   "%s file used on %s: %s" %
                                   (extension, basename, fname))
