'''This file manages the statistics collected by the BCFG2 Server'''
__revision__ = '$Revision: $'

from elementtree.ElementTree import XML, SubElement, Element
from xml.parsers.expat import ExpatError
from syslog import syslog, LOG_INFO, LOG_ERR
from time import asctime, localtime, time

class Statistics(object):
    '''Manages the memory and file copy of statistics collected about client runs'''
    __min_write_delay__ = 30

    def __init__(self, filename):
        self.filename = filename
        self.element = Element('Dummy')
        self.dirty = 0
        self.lastwrite = 0
        self.ReadFromFile()

    def pretty_print(self, element, level=0):
        '''Produce a pretty-printed text representation of element'''
        if element.text:
            fmt = "%s<%%s %%s>%%s</%%s>" % (level*" ")
            data = (element.tag, (" ".join(["%s='%s'" % x for x in element.attrib.iteritems()])),
                    element.text, element.tag)
        if element._children:
            fmt = "%s<%%s %%s>\n" % (level*" ",) + (len(element._children) * "%s") + "%s</%%s>\n" % (level*" ")
            data = (element.tag, ) + (" ".join(["%s='%s'" % x for x in element.attrib.iteritems()]),)
            data += tuple([self.pretty_print(x, level+2) for x in element._children]) + (element.tag, )
        else:
            fmt = "%s<%%s %%s/>\n" % (level * " ")
            data = (element.tag, " ".join(["%s='%s'" % x for x in element.attrib.iteritems()]))
        return fmt % data

    def WriteBack(self, force=0):
        '''Write statistics changes back to persistent store'''
        if (self.dirty and (self.lastwrite + self.__min_write_delay__ <= time()) ) \
                or force:
            #syslog(LOG_INFO, "Statistics: Updated statistics.xml")
            fout = open(self.filename, 'w')
            fout.write(self.pretty_print(self.element))
            fout.close()
            self.dirty = 0
            self.lastwrite = time()

    def ReadFromFile(self):
        '''Reads current state regarding statistics'''
        try:
            fin = open(self.filename, 'r')
            data = fin.read()
            fin.close()
            self.element = XML(data)
            self.dirty = 0
            #syslog(LOG_INFO, "Statistics: Read in statistics.xml")
        except (IOError, ExpatError):
            syslog(LOG_ERR, "Statistics: Failed to parse %s"%(self.filename))
            self.element = Element('ConfigStatistics')
            self.WriteBack()
            self.dirty = 0


    def updateStats(self, xml, client):
        '''Updates the statistics of a current node with new data'''

        # Current policy: 
        # - Keep latest clean run for clean nodes
        # - Keep latest clean and dirty run for dirty nodes
        newstat =  xml.find('Statistics')

        if newstat.get('state') == 'clean':
            node_dirty = 0
        else:
            node_dirty = 1

        # Find correct node entry in stats data
        # The following list comprehension should be guarenteed to return at
        # most one result
        nodes = [elem for elem in self.element.findall('Node') if elem.get('name') == client]
        nl = len(nodes)
        if nl == 0:
            # Create an entry for this node
            node = SubElement(self.element, 'Node', name=client)
        elif nl == 1 and not node_dirty:
            # Delete old instance
            self.element.remove(nodes[0])
            node = SubElement(self.element, 'Node', name=client)
        elif nl == 1 and node_dirty:
            # Delete old dirty statistics entry
            node = nodes[0]
            for elem in [elem for elem in node.findall('Statistics') if elem.get('state') == 'dirty']:
                node.remove(elem)
        else:
            # Shouldn't be reached
            syslog(LOG_ERR, "Statistics: Duplicate node entry for %s"%(client))

        # Set current time for stats
        newstat.set('time', asctime(localtime()))

        # Add statistic
        node.append(newstat)

        # Set dirty
        self.dirty = 1
