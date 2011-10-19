import os
import sys
import lxml.etree
import logging
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Packages.Source import SourceInitError

logger = logging.getLogger("Packages")

class PackagesSources(Bcfg2.Server.Plugin.SingleXMLFileBacked,
                      Bcfg2.Server.Plugin.StructFile):
    __identifier__ = None
    
    def __init__(self, filename, cachepath, fam, packages, config):
        try:
            Bcfg2.Server.Plugin.SingleXMLFileBacked.__init__(self,
                                                             filename,
                                                             fam)
        except OSError:
            err = sys.exc_info()[1]
            msg = "Packages: Failed to read configuration file: %s" % err
            if not os.path.exists(self.name):
                msg += " Have you created it?"
            logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginInitError(msg)
        Bcfg2.Server.Plugin.StructFile.__init__(self, filename)
        self.cachepath = cachepath
        self.config = config
        if not os.path.exists(self.cachepath):
            # create cache directory if needed
            os.makedirs(self.cachepath)
        self.pkg_obj = packages
        self.parsed = set()
        self.loaded = False

    def HandleEvent(self, event=None):
        Bcfg2.Server.Plugin.SingleXMLFileBacked.HandleEvent(self, event=event)
        if event.filename != self.name:
            self.parsed.add(os.path.basename(event.filename))

        if sorted(list(self.parsed)) == sorted(self.extras):
            logger.info("Reloading Packages plugin")
            self.pkg_obj.Reload()
            self.loaded = True

    def Index(self):
        Bcfg2.Server.Plugin.SingleXMLFileBacked.Index(self)
        self.entries = []
        for xsource in self.xdata.findall('.//Source'):
            source = self.source_from_xml(xsource)
            if source is not None:
                self.entries.append(source)

    def source_from_xml(self, xsource):
        """ create a *Source object from its XML representation in
        sources.xml """
        stype = xsource.get("type")
        if stype is None:
            logger.error("Packages: No type specified for source, skipping")
            return None

        try:
            module = getattr(__import__("Bcfg2.Server.Plugins.Packages.%s" %
                                        stype.title()).Server.Plugins.Packages,
                             stype.title())
            cls = getattr(module, "%sSource" % stype.title())
        except (ImportError, AttributeError):
            logger.error("Packages: Unknown source type %s" % stype)
            return None

        try:
            source = cls(self.cachepath, xsource, self.config)
        except SourceInitError:
            err = sys.exc_info()[1]
            logger.error("Packages: %s" % err)
            source = None

        return source

    def __getitem__(self, key):
        return self.entries[key]

    def __repr__(self):
        return "PackagesSources: %s" % repr(self.entries)

    def __str__(self):
        return "PackagesSources: %s" % str(self.entries)
