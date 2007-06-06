'''This file manages the statistics collected by the BCFG2 Server'''
__revision__ = '$Revision$'

from lxml.etree import XML, SubElement, Element, XMLSyntaxError
from time import asctime, localtime, time, strptime, mktime

import logging, lxml.etree, os

class Statistics(object):
    '''Manages the memory and file copy of statistics collected about client runs'''
    __min_write_delay__ = 30

    def __init__(self, filename):
        self.filename = filename
        self.element = Element('Dummy')
        self.dirty = 0
        self.lastwrite = 0
        self.logger = logging.getLogger('Bcfg2.Server.Statistics')
        self.ReadFromFile()

    def WriteBack(self, force=0):
        '''Write statistics changes back to persistent store'''
        if (self.dirty and (self.lastwrite + self.__min_write_delay__ <= time()) ) \
                or force:
            #syslog(LOG_INFO, "Statistics: Updated statistics.xml")
            try:
                fout = open(self.filename + '.new', 'w')
            except IOError, ioerr:
                self.logger.error("Failed to open %s for writing: %s" % (self.filename + '.new', ioerr))
            else:
                fout.write(lxml.etree.tostring(self.element))
                fout.close()
                os.rename(self.filename + '.new', self.filename)
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
        except (IOError, XMLSyntaxError):
            self.logger.error("Creating new statistics file %s"%(self.filename))
            self.element = Element('ConfigStatistics')
            self.WriteBack()
            self.dirty = 0

    def updateStats(self, xml, client):
        '''Updates the statistics of a current node with new data'''

        # Current policy: 
        # - Keep anything less than 24 hours old
        #   - Keep latest clean run for clean nodes
        #   - Keep latest clean and dirty run for dirty nodes
        newstat =  xml.find('Statistics')

        if newstat.get('state') == 'clean':
            node_dirty = 0
        else:
            node_dirty = 1

        # Find correct node entry in stats data
        # The following list comprehension should be guarenteed to return at
        # most one result
        nodes = [elem for elem in self.element.findall('Node') if elem.get('name') == client]
        nummatch = len(nodes)
        if nummatch == 0:
            # Create an entry for this node
            node = SubElement(self.element, 'Node', name=client)
        elif nummatch == 1 and not node_dirty:
            # Delete old instance
            node = nodes[0]
            [node.remove(elem) for elem in node.findall('Statistics') if self.isOlderThan24h(elem.get('time'))]
        elif nummatch == 1 and node_dirty:
            # Delete old dirty statistics entry
            node = nodes[0]
            [node.remove(elem) for elem in node.findall('Statistics') if (elem.get('state') == 'dirty' and self.isOlderThan24h(elem.get('time')))]
        else:
            # Shouldn't be reached
            self.logger.error("Duplicate node entry for %s"%(client))

        # Set current time for stats
        newstat.set('time', asctime(localtime()))

        # Add statistic
        node.append(newstat)

        # Set dirty
        self.dirty = 1
        self.WriteBack()


    def isOlderThan24h(self, testTime):
        '''Helper function to determine if <time> string is older than 24 hours'''
        now = time()
        utime = mktime(strptime(testTime))
        secondsPerDay = 60*60*24

        return (now-utime) > secondsPerDay

