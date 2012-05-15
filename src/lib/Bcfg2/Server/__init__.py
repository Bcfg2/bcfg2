"""This is the set of modules for Bcfg2.Server."""

import lxml.etree

__all__ = ["Admin", "Core", "FileMonitor", "Plugin", "Plugins",
           "Hostbase", "Reports", "Snapshots", "XMLParser"]

XMLParser = lxml.etree.XMLParser(remove_blank_text=True)
