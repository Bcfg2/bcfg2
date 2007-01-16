'''XML lib compatibility layer for the Bcfg2 client'''
__revision__ = '$Revision$'

# library will use lxml, then builtin xml.etree, then ElementTree

try:
    from lxml.etree import Element, SubElement, XML, tostring
    from lxml.etree import XMLSyntaxError as ParseError
    driver = 'lxml'
except ImportError:
    # lxml not available 
    try:
        from xml.etree.ElementTree import Element, SubElement, XML, tostring
        from xml.parsers.expat import ExpatError as ParseError
        driver = 'etree-py'
    except ImportError:
        try:
            from elementtree.ElementTree import Element, SubElement, XML, tostring
            from xml.parsers.expat import ExpatError as ParseError
            driver = 'etree'
        except ImportError:
            print "Failed to load lxml, xml.etree and elementtree.ElementTree"
            print "Cannot continue"
            raise SystemExit, 1

len([Element, SubElement, XML, tostring, ParseError])
