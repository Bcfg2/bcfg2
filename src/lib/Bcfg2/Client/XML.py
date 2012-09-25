'''XML lib compatibility layer for the Bcfg2 client'''

# library will use lxml, then builtin xml.etree, then ElementTree

# pylint: disable=E0611,W0611,W0613,C0103

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

        def tostring(el, encoding=None, xml_declaration=None):
            """ tostring implementation compatible with lxml """
            return xml.etree.ElementTree.tostring(el, encoding=encoding)

        driver = 'etree-py'
    except ImportError:
        try:
            from elementtree.ElementTree import Element, SubElement, XML, \
                tostring
            driver = 'etree'
            import elementtree.ElementTree
            Element = elementtree.ElementTree.Element
            SubElement = elementtree.ElementTree.SubElement
            XML = elementtree.ElementTree.XML

            def tostring(el, encoding=None, xml_declaration=None):
                """ tostring implementation compatible with lxml """
                return elementtree.ElementTree.tostring(el)

        except ImportError:
            print("Failed to load lxml, xml.etree or elementtree.ElementTree")
            print("Cannot continue")
            raise SystemExit(1)
