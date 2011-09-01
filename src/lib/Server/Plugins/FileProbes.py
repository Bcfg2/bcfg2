""" This module allows you to probe a client for a file, which is then
added to the specification.  On subsequent runs, the file will be
replaced on the client if it is missing; if it has changed on the
client, it can either be updated in the specification or replaced on
the client """
__revision__ = '$Revision: 1465 $'

import os
import errno
import binascii
import lxml.etree
import Bcfg2.Options
import Bcfg2.Server.Plugin

probecode = """#!/usr/bin/env python

import os
import pwd
import grp
import binascii
import lxml.etree

path = "%s"

if not os.path.exists(path):
    print "%%s does not exist" %% path
    raise SystemExit(1)

stat = os.stat(path)
data = lxml.etree.Element("ProbedFileData",
                          name=path,
                          owner=pwd.getpwuid(stat[4])[0],
                          group=grp.getgrgid(stat[5])[0],
                          perms=oct(stat[0] & 07777))
data.text = binascii.b2a_base64(open(path).read())
print lxml.etree.tostring(data)
"""

class FileProbesConfig(Bcfg2.Server.Plugin.SingleXMLFileBacked,
                       Bcfg2.Server.Plugin.StructFile):
    """ Config file handler for FileProbes """
    def __init__(self, filename, fam):
        Bcfg2.Server.Plugin.SingleXMLFileBacked.__init__(self, filename, fam)
        Bcfg2.Server.Plugin.StructFile.__init__(self, filename)


class FileProbes(Bcfg2.Server.Plugin.Plugin,
                 Bcfg2.Server.Plugin.Probing):
    """ This module allows you to probe a client for a file, which is then
    added to the specification.  On subsequent runs, the file will be
    replaced on the client if it is missing; if it has changed on the
    client, it can either be updated in the specification or replaced on
    the client """

    name = 'FileProbes'
    experimental = True
    __version__ = '$Id$'
    __author__ = 'stpierreca@ornl.gov'

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Probing.__init__(self)
        self.config = FileProbesConfig(os.path.join(self.data, 'config.xml'),
                                       core.fam)
        self.entries = dict()
        self.probes = dict()

    def GetProbes(self, metadata):
        """Return a set of probes for execution on client."""
        if metadata.hostname not in self.probes:
            cfg = self.core.plugins['Cfg']
            self.entries[metadata.hostname] = dict()
            self.probes[metadata.hostname] = []
            for entry in self.config.Match(metadata):
                path = entry.get("name")
                # do not probe for files that are already in Cfg and
                # for which update is false; we can't possibly do
                # anything with the data we get from such a probe
                try:
                    if (entry.get('update', 'false').lower() == "false" and
                        cfg.entries[path].get_pertinent_entries(entry,
                                                                metadata)):
                        continue
                except (KeyError, Bcfg2.Server.Plugin.PluginExecutionError):
                    pass
                self.entries[metadata.hostname][path] = entry
                probe = lxml.etree.Element('probe', name=path,
                                           source=self.name,
                                           interpreter="/usr/bin/env python")
                probe.text = probecode % path
                self.probes[metadata.hostname].append(probe)
                self.logger.debug("Adding file probe for %s to %s" %
                                  (path, metadata.hostname))
        return self.probes[metadata.hostname]

    def ReceiveData(self, metadata, datalist):
        """Receive data from probe."""
        self.logger.debug("Receiving file probe data from %s" %
                          metadata.hostname)

        for data in datalist:
            if data.text is None:
                self.logger.error("Got null response to %s file probe from %s" %
                                  (data.get('name'), metadata.hostname))
            else:
                self.logger.debug("%s:fileprobe:%s:%s" %
                                  (metadata.hostname,
                                   data.get("name"),
                                   data.text))
                try:
                    filedata = lxml.etree.XML(data.text)
                    self.write_file(filedata, metadata)
                except lxml.etree.XMLSyntaxError:
                    # if we didn't get XML back from the probe, assume
                    # it's an error message
                    self.logger.error(data.text)

    def write_file(self, data, metadata):
        """Write the probed file data to the bcfg2 specification."""
        filename = data.get("name")
        contents = binascii.a2b_base64(data.text)
        entry = self.entries[metadata.hostname][filename]
        cfg = self.core.plugins['Cfg']
        specific = "%s.H_%s" % (os.path.basename(filename), metadata.hostname)
        # we can't use os.path.join() for this because specific
        # already has a leading /, which confuses os.path.join()
        fileloc = "%s%s" % (cfg.data, os.path.join(filename, specific))
        if filename not in cfg.entries.keys():
            self.logger.info("Writing new probed file %s" % fileloc)    
            try:
                os.makedirs(os.path.dirname(fileloc))
            except OSError, err:
                if err.errno == errno.EEXIST:
                    pass
                else:
                    raise
            open(fileloc, 'wb').write(contents)

            infoxml = os.path.join("%s%s" % (cfg.data, filename),
                                   "info.xml")
            self.write_infoxml(infoxml, entry, data)
        else:
            try:
                cfgentry = \
                    cfg.entries[filename].get_pertinent_entries(entry,
                                                                metadata)[0]
            except Bcfg2.Server.Plugin.PluginExecutionError:
                self.logger.info("Writing new probed file %s" % fileloc)
                open(fileloc, 'wb').write(contents)
                return
            
            if cfgentry.data == contents:
                self.logger.debug("Existing %s contents match probed contents" %
                                  filename)
            elif (entry.get('update', 'false').lower() == "true"):
                self.logger.info("Writing updated probed file %s" % fileloc)
                open(fileloc, 'wb').write(contents)
            else:
                self.logger.info("Skipping updated probed file %s" % fileloc)
                        
    def write_infoxml(self, infoxml, entry, data):
        """ write an info.xml for the file """
        self.logger.info("Writing info.xml at %s for %s" %
                         (infoxml, data.get("name")))
        info = \
            lxml.etree.Element("Info",
                               owner=data.get("owner",
                                              Bcfg2.Options.MDATA_OWNER.value),
                               group=data.get("group",
                                              Bcfg2.Options.MDATA_GROUP.value),
                               perms=data.get("perms",
                                              Bcfg2.Options.MDATA_PERMS.value),
                               encoding=entry.get("encoding",
                                                  Bcfg2.Options.ENCODING.value))
        
        root = lxml.etree.Element("FileInfo")
        root.append(info)
        open(infoxml, "w").write(lxml.etree.tostring(root,
                                                     pretty_print=True))
