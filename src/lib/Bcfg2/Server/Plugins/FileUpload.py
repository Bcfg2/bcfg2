"""This provides bundle clauses with translation functionality."""

import copy
import logging
import lxml.etree
import os
import os.path
import errno
import re
import sys
import Bcfg2.Options
import Bcfg2.Server
import Bcfg2.Server.Plugin
import Bcfg2.Server.Lint
from Bcfg2.Compat import b64decode

try:
    import genshi.template.base
    from Bcfg2.Server.Plugins.TGenshi import removecomment, TemplateFile
    HAS_GENSHI = True
except ImportError:
    HAS_GENSHI = False


SETUP = None

PROBECODE = """#!/usr/bin/env python

import os
import sys
import pwd
import grp
import Bcfg2.Client.XML
try:
    from Bcfg2.Compat import b64encode, oct_mode
except ImportError:
    from base64 import b64encode
    oct_mode = oct

path = "%s"

if not os.path.exists(path):
    sys.stderr.write("%%s does not exist" %% path)
    raise SystemExit(0)

try:
    stat = os.stat(path)
except:
    sys.stderr.write("Could not stat %%s: %%s" %% (path, sys.exc_info()[1]))
    raise SystemExit(0)

try:
   own=pwd.getpwuid(stat[4])[0]
except:
   own="!missing!"

try:
   grupp=grp.getgrgid(stat[5])[0]
except:
   grupp="!missing!"

data = Bcfg2.Client.XML.Element("ProbedFileData",
                                name=path,
                                owner=own,
                                group=grupp,
                                mode=oct_mode(stat[0] & 4095))
try:
    data.text = b64encode(open(path).read())
except:
    sys.stderr.write("Could not read %%s: %%s" %% (path, sys.exc_info()[1]))
    raise SystemExit(0)
print(Bcfg2.Client.XML.tostring(data, xml_declaration=False).decode('UTF-8'))
"""


class BundleFile(Bcfg2.Server.Plugin.StructFile):
    """ Representation of a bundle XML file """
    def get_xml_value(self, metadata):
        """ get the XML data that applies to the given client """
        bundlename = os.path.splitext(os.path.basename(self.name))[0]
        bundle = lxml.etree.Element('Bundle', name=bundlename)
        for item in self.Match(metadata):
            bundle.append(copy.copy(item))
        return bundle
        
if HAS_GENSHI:
    class BundleTemplateFile(TemplateFile,
                             Bcfg2.Server.Plugin.StructFile):
        """ Representation of a Genshi-templated bundle XML file """

        def __init__(self, name, specific, encoding, fam=None):
            TemplateFile.__init__(self, name, specific, encoding)
            Bcfg2.Server.Plugin.StructFile.__init__(self, name, fam=fam)
            self.logger = logging.getLogger(name)

        def get_xml_value(self, metadata):
            """ get the rendered XML data that applies to the given
            client """
            if not hasattr(self, 'template'):
                msg = "No parsed template information for %s" % self.name
                self.logger.error(msg)
                raise Bcfg2.Server.Plugin.PluginExecutionError(msg)
            stream = self.template.generate(
                metadata=metadata,
                repo=SETUP['repo']).filter(removecomment)
            data = lxml.etree.XML(stream.render('xml',
                                                strip_whitespace=False),
                                  parser=Bcfg2.Server.XMLParser)
            bundlename = os.path.splitext(os.path.basename(self.name))[0]
            bundle = lxml.etree.Element('Bundle', name=bundlename)
            for item in self.Match(metadata, data):
                bundle.append(copy.deepcopy(item))
            return bundle
            
        def Match(self, metadata, xdata):  # pylint: disable=W0221
            """Return matching fragments of parsed template."""
            rv = []
            for child in xdata.getchildren():
                rv.extend(self._match(child, metadata))
            self.logger.debug("File %s got %d match(es)" % (self.name,
                                                            len(rv)))
            return rv

    class SGenshiTemplateFile(BundleTemplateFile):
        """ provided for backwards compat with the deprecated SGenshi
        plugin """
        pass


class FileUpload(Bcfg2.Server.Plugin.Plugin,
              Bcfg2.Server.Plugin.Structure,
              Bcfg2.Server.Plugin.XMLDirectoryBacked,
	      Bcfg2.Server.Plugin.Probing):
    """ The bundler creates dependent clauses based on the
    bundle/translation scheme from Bcfg1. """
    __author__ = 'tomaszov@hotmail.com'
    patterns = re.compile(r'^(?P<name>.*)\.(xml|genshi)$')

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Structure.__init__(self)
        Bcfg2.Server.Plugin.Probing.__init__(self)
        self.encoding = core.setup['encoding']
        self.__child__ = self.template_dispatch
        Bcfg2.Server.Plugin.XMLDirectoryBacked.__init__(self, self.data,
                                                        self.core.fam)
        global SETUP
        

        SETUP = core.setup

        self.entries = dict()
        self.probes = dict()

    def template_dispatch(self, name, _):
        """ Add the correct child entry type to Bundler depending on
        whether the XML file in question is a plain XML file or a
        templated bundle """
        bundle = lxml.etree.parse(name, parser=Bcfg2.Server.XMLParser)
        nsmap = bundle.getroot().nsmap
        if (name.endswith('.genshi') or
            ('py' in nsmap and
             nsmap['py'] == 'http://genshi.edgewall.org/')):
            if HAS_GENSHI:
                spec = Bcfg2.Server.Plugin.Specificity()
                return BundleTemplateFile(name, spec, self.encoding,
                                          fam=self.core.fam)
            else:
                raise Bcfg2.Server.Plugin.PluginExecutionError("Genshi not "
                                                               "available: %s"
                                                               % name)
        else:
            return BundleFile(name, fam=self.fam)

    def BuildStructures(self, metadata):
    
	"""Build all structures for client (metadata)."""
	bundleset2 = []

	return bundleset2
	                    

    def GetProbes(self, metadata):
        """Build all structures for client (metadata)."""

        self.core.metadata_cache.expire()
        metadata = self.core.build_metadata(metadata.hostname)        

        bundleset = []

        bundle_entries = {}

        
        for key, item in self.entries.items():
    	 try:
            bundle_entries.setdefault(
                self.patterns.match(os.path.basename(key)).group('name'),bundleset).append(item)
         except:
        	self.logger.error("WTF")

        	

        for bundlename in metadata.bundles:
    	    items = []
            try:
                entries = bundle_entries[bundlename]
                self.logger.info("entries: %s" % entries)

            except KeyError:
                self.logger.error("Bundler: Bundle %s does not exist" %
                                  bundlename)
                continue
            try:
                bundleset.append(entries[0].get_xml_value(metadata))
                items = entries[0].get_xml_value(metadata).getchildren()
                self.logger.info("info: %s" % entries[0].get_xml_value(metadata).getchildren())
            except genshi.template.base.TemplateError:
                err = sys.exc_info()[1]
                self.logger.error("Bundler: Failed to render templated bundle "
                                  "%s: %s" % (bundlename, err))
            except:
                self.logger.error("Bundler: Unexpected bundler error for %s" %
                                  bundlename, exc_info=1)
    
    	    """Return a set of probes for execution on client."""

            cfg = self.core.plugins['Cfg']
            self.entries[metadata.hostname] = dict()
            self.probes[metadata.hostname] = []
            for entry in items:
        	path = entry.get('name')
    	        self.logger.info("info: %s" % path)
                # do not probe for files that are already in Cfg and
                # for which update is false; we can't possibly do
                # anything with the data we get from such a probe
                if (entry.get('update', 'false').lower() == "false" and
                    not cfg.has_generator(entry, metadata)):
                    continue
                self.entries[metadata.hostname][path] = entry
                probe = lxml.etree.Element('probe', name=path,
                                           source=self.name,
                                           interpreter="/usr/bin/env python")
                probe.text = PROBECODE % path
                self.probes[metadata.hostname].append(probe)
                self.debug_log("Adding file probe for %s to %s" %
                               (path, metadata.hostname))
	self.logger.info("info1: %s" % bundle_entries.values())
        return self.probes[metadata.hostname]
    
    def ReceiveData(self, metadata, datalist):
        """Receive data from probe."""
        self.debug_log("Receiving file probe data from %s" % metadata.hostname)

        for data in datalist:
	    self.logger.info("datatext: %s" % data.text)
            if data.text is None:
                self.logger.error("Got null response to %s file probe from %s"
                                  % (data.get('name'), metadata.hostname))
            else:
                try:
                    self.write_data(
                        lxml.etree.XML(data.text,
                                       parser=Bcfg2.Server.XMLParser),
                        metadata)
                except lxml.etree.XMLSyntaxError:
                    # if we didn't get XML back from the probe, assume
                    # it's an error message
                    self.logger.error(data.text)


    def write_data(self, data, metadata):
        """Write the probed file data to the bcfg2 specification."""
        filename = data.get("name")

        if data.text is not None:
	        contents = b64decode(data.text)
	else: 
		contents = ''

        entry = self.entries[metadata.hostname][filename]
        cfg = self.core.plugins['Cfg']
        specific = "%s.H_%s" % (os.path.basename(filename), metadata.hostname)
        # we can't use os.path.join() for this because specific
        # already has a leading /, which confuses os.path.join()
        fileloc = os.path.join(cfg.data,
                               os.path.join(filename, specific).lstrip("/"))

        create = False
        try:
            cfg.entries[filename].bind_entry(entry, metadata)
        except (KeyError, Bcfg2.Server.Plugin.PluginExecutionError):
            create = True

        # get current entry data
        if entry.text and entry.get("encoding") == "base64":
            entrydata = b64decode(entry.text)
        else:
            entrydata = entry.text

        if create:
            self.logger.info("Writing new probed file %s" % fileloc)
            self.write_file(fileloc, contents)
            self.verify_file(filename, contents, metadata)
            infoxml = os.path.join(cfg.data, filename.lstrip("/"), "info.xml")
            self.write_infoxml(infoxml, entry, data)
        elif entrydata == contents:
            self.debug_log("Existing %s contents match probed contents" %
                           filename)
            return
        elif (entry.get('update', 'false').lower() == "true"):
            self.logger.info("Writing updated probed file %s" % fileloc)
            self.write_file(fileloc, contents)
            self.verify_file(filename, contents, metadata)
        else:
            self.logger.info("Skipping updated probed file %s" % fileloc)
            return


    def write_file(self, fileloc, contents):
        """ Write the probed file to disk """
        try:
            os.makedirs(os.path.dirname(fileloc))
        except OSError:
            err = sys.exc_info()[1]
            if err.errno == errno.EEXIST:
                pass
            else:
                self.logger.error("Could not create parent directories for "
                                  "%s: %s" % (fileloc, err))
                return

        try:
            open(fileloc, 'wb').write(contents)
        except IOError:
            err = sys.exc_info()[1]
            self.logger.error("Could not write %s: %s" % (fileloc, err))
            return


    def verify_file(self, filename, contents, metadata):
        """ Service the FAM events queued up by the key generation so
        the data structure entries will be available for binding.

        NOTE: We wait for up to ten seconds. There is some potential
        for race condition, because if the file monitor doesn't get
        notified about the new key files in time, those entries won't
        be available for binding. In practice, this seems "good
        enough"."""
        entry = self.entries[metadata.hostname][filename]
        cfg = self.core.plugins['Cfg']
        tries = 0
        updated = False
        while not updated:
            if tries >= 10:
                self.logger.error("%s still not registered" % filename)
                return
            self.core.fam.handle_events_in_interval(1)
            try:
                cfg.entries[filename].bind_entry(entry, metadata)
            except Bcfg2.Server.Plugin.PluginExecutionError:
                tries += 1
                continue

            # get current entry data
            if entry.get("encoding") == "base64":
                entrydata = b64decode(entry.text)
            else:
                entrydata = entry.text
            if entrydata == contents:
                updated = True
            tries += 1

    def write_infoxml(self, infoxml, entry, data):
        """ write an info.xml for the file """
        if os.path.exists(infoxml):
            return

        self.logger.info("Writing %s for %s" % (infoxml, data.get("name")))
        info = lxml.etree.Element(
            "Info",
            owner=data.get("owner", Bcfg2.Options.MDATA_OWNER.value),
            group=data.get("group", Bcfg2.Options.MDATA_GROUP.value),
            mode=data.get("mode", Bcfg2.Options.MDATA_MODE.value),
            encoding=entry.get("encoding", Bcfg2.Options.ENCODING.value))

        root = lxml.etree.Element("FileInfo")
        root.append(info)
        try:
            root.getroottree().write(infoxml, xml_declaration=False,
                                     pretty_print=True)
        except IOError:
            err = sys.exc_info()[1]
            self.logger.error("Could not write %s: %s" % (infoxml, err))
            return



class BundlerLint(Bcfg2.Server.Lint.ServerPlugin):
    """ Perform various :ref:`Bundler
    <server-plugins-structures-bundler-index>` checks. """

    def Run(self):
        self.missing_bundles()
        for bundle in self.core.plugins['Bundler'].entries.values():
            if (self.HandlesFile(bundle.name) and
                (not HAS_GENSHI or
                 not isinstance(bundle, BundleTemplateFile))):
                self.bundle_names(bundle)

    @classmethod
    def Errors(cls):
        return {"bundle-not-found": "error",
                "inconsistent-bundle-name": "warning"}

    def missing_bundles(self):
        """ Find bundles listed in Metadata but not implemented in
        Bundler. """
        if self.files is None:
            # when given a list of files on stdin, this check is
            # useless, so skip it
            groupdata = self.metadata.groups_xml.xdata
            ref_bundles = set([b.get("name")
                               for b in groupdata.findall("//Bundle")])

            allbundles = self.core.plugins['Bundler'].entries.keys()
            for bundle in ref_bundles:
                xmlbundle = "%s.xml" % bundle
                genshibundle = "%s.genshi" % bundle
                if (xmlbundle not in allbundles and
                    genshibundle not in allbundles):
                    self.LintError("bundle-not-found",
                                   "Bundle %s referenced, but does not exist" %
                                   bundle)

    def bundle_names(self, bundle):
        """ Verify bundle name attribute matches filename.

        :param bundle: The bundle to verify
        :type bundle: Bcfg2.Server.Plugins.Bundler.BundleFile
        """
        try:
            xdata = lxml.etree.XML(bundle.data)
        except AttributeError:
            # genshi template
            xdata = lxml.etree.parse(bundle.template.filepath).getroot()

        fname = os.path.splitext(os.path.basename(bundle.name))[0]
        bname = xdata.get('name')
        if fname != bname:
            self.LintError("inconsistent-bundle-name",
                           "Inconsistent bundle name: filename is %s, "
                           "bundle name is %s" % (fname, bname))
