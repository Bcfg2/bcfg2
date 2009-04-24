'''XML lib compatibility layer for the Bcfg2 client'''
__revision__ = '$Revision$'

# library will use lxml, then builtin xml.etree, then ElementTree

try:
    from lxml.etree import Element, SubElement, XML, tostring
    from lxml.etree import XMLSyntaxError as ParseError
    driver = 'lxml'
except ImportError:
    # lxml not available
    from xml.parsers.expat import ExpatError as ParseError
    try:
        import xml.etree.ElementTree
        Element = xml.etree.ElementTree.Element
        SubElement = xml.etree.ElementTree.SubElement
        XML = xml.etree.ElementTree.XML
        def tostring(e, encoding=None, xml_declaration=None):
            return xml.etree.ElementTree.tostring(e, encoding=encoding)
        driver = 'etree-py'
    except ImportError:
        try:
            from elementtree.ElementTree import Element, SubElement, XML, tostring
            driver = 'etree'
            import elementtree.ElementTree
            Element = elementtree.ElementTree.Element
            SubElement = elementtree.ElementTree.SubElement
            XML = elementtree.ElementTree.XML
            def tostring(e, encoding=None, xml_declaration=None):
                return elementtree.ElementTree.tostring(e)

        except ImportError:
            print("Failed to load lxml, xml.etree and elementtree.ElementTree")
            print("Cannot continue")
            raise SystemExit(1)

len([Element, SubElement, XML, tostring, ParseError])
