import os
import sys
import lxml.etree
import Bcfg2.Server.Plugin
from Bcfg2.Server.Plugins.Packages.Source import SourceInitError

class PackagesSources(Bcfg2.Server.Plugin.StructFile,
                      Bcfg2.Server.Plugin.Debuggable):
    __identifier__ = None

    def __init__(self, filename, cachepath, fam, packages, setup):
        Bcfg2.Server.Plugin.Debuggable.__init__(self)
        try:
            Bcfg2.Server.Plugin.StructFile.__init__(self, filename, fam=fam,
                                                    should_monitor=True)
        except OSError:
            err = sys.exc_info()[1]
            msg = "Packages: Failed to read configuration file: %s" % err
            if not os.path.exists(self.name):
                msg += " Have you created it?"
            self.logger.error(msg)
            raise Bcfg2.Server.Plugin.PluginInitError(msg)
        self.cachepath = cachepath
        self.setup = setup
        if not os.path.exists(self.cachepath):
            # create cache directory if needed
            try:
                os.makedirs(self.cachepath)
            except OSError:
                err = sys.exc_info()[1]
                self.logger.error("Could not create Packages cache at %s: %s" %
                                  (self.cachepath, err))
        self.pkg_obj = packages
        self.parsed = set()

    def toggle_debug(self):
        Bcfg2.Server.Plugin.Debuggable.toggle_debug(self)
        for source in self.entries:
            source.toggle_debug()

    def HandleEvent(self, event=None):
        Bcfg2.Server.Plugin.XMLFileBacked.HandleEvent(self, event=event)
        if event and event.filename != self.name:
            for fpath in self.extras:
                if fpath == os.path.abspath(event.filename):
                    self.parsed.add(fpath)
                    break

        if self.loaded:
            self.logger.info("Reloading Packages plugin")
            self.pkg_obj.Reload()

    @property
    def loaded(self):
        return sorted(list(self.parsed)) == sorted(self.extras)

    def Index(self):
        Bcfg2.Server.Plugin.XMLFileBacked.Index(self)
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
            self.logger.error("Packages: No type specified for source, "
                              "skipping")
            return None

        try:
            module = getattr(__import__("Bcfg2.Server.Plugins.Packages.%s" %
                                        stype.title()).Server.Plugins.Packages,
                             stype.title())
            cls = getattr(module, "%sSource" % stype.title())
        except (ImportError, AttributeError):
            ex = sys.exc_info()[1]
            self.logger.error("Packages: Unknown source type %s (%s)" % (stype, ex))
            return None

        try:
            source = cls(self.cachepath, xsource, self.setup)
        except SourceInitError:
            err = sys.exc_info()[1]
            self.logger.error("Packages: %s" % err)
            source = None

        return source

    def __getitem__(self, key):
        return self.entries[key]

    def __repr__(self):
        return "PackagesSources: %s" % repr(self.entries)

    def __str__(self):
        return "PackagesSources: %s sources" % len(self.entries)

    def __len__(self):
        return len(self.entries)
