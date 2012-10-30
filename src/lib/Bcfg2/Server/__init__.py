"""This is the set of modules for Bcfg2.Server."""

import lxml.etree

__all__ = ["Admin", "Core", "FileMonitor", "Plugin", "Plugins",
           "Reports", "XMLParser", "XI", "XI_NAMESPACE"]

XI = 'http://www.w3.org/2001/XInclude'
XI_NAMESPACE = '{%s}' % XI

# pylint: disable=C0103
XMLParser = lxml.etree.XMLParser(remove_blank_text=True)
