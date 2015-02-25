"""This is the set of modules for Bcfg2.Server."""

import lxml.etree

XI = 'http://www.w3.org/2001/XInclude'
XI_NAMESPACE = '{%s}' % XI

# pylint: disable=invalid-name
XMLParser = lxml.etree.XMLParser(remove_blank_text=True)

core = None
