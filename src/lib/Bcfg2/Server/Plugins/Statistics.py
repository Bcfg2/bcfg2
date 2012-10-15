'''This file manages the statistics collected by the BCFG2 Server'''

import copy
import difflib
import logging
import lxml.etree
import os
import sys
from time import asctime, localtime, time, strptime, mktime
import threading
from Bcfg2.Compat import b64decode
import Bcfg2.Server.Plugin


class StatisticsStore(object):
    """Manages the memory and file copy of statistics collected about client runs."""
    __min_write_delay__ = 0

    def __init__(self, filename):
        self.filename = filename
        self.element = lxml.etree.Element('Dummy')
        self.dirty = 0
        self.lastwrite = 0
        self.logger = logging.getLogger('Bcfg2.Server.Statistics')
        self.ReadFromFile()

    def WriteBack(self, force=0):
        """Write statistics changes back to persistent store."""
        if (self.dirty and (self.lastwrite + self.__min_write_delay__ <= time())) \
                or force:
            try:
                fout = open(self.filename + '.new', 'w')
            except IOError:
                ioerr = sys.exc_info()[1]
                self.logger.error("Failed to open %s for writing: %s" % (self.filename + '.new', ioerr))
            else:
                fout.write(lxml.etree.tostring(self.element,
                                               xml_declaration=False).decode('UTF-8'))
                fout.close()
                os.rename(self.filename + '.new', self.filename)
                self.dirty = 0
                self.lastwrite = time()

    def ReadFromFile(self):
        """Reads current state regarding statistics."""
        try:
            fin = open(self.filename, 'r')
            data = fin.read()
            fin.close()
            self.element = lxml.etree.XML(data)
            self.dirty = 0
        except (IOError, lxml.etree.XMLSyntaxError):
            self.logger.error("Creating new statistics file %s"%(self.filename))
            self.element = lxml.etree.Element('ConfigStatistics')
            self.WriteBack()
            self.dirty = 0

    def updateStats(self, xml, client):
        """Updates the statistics of a current node with new data."""

        # Current policy:
        # - Keep anything less than 24 hours old
        #   - Keep latest clean run for clean nodes
        #   - Keep latest clean and dirty run for dirty nodes
        newstat = xml.find('Statistics')

        if newstat.get('state') == 'clean':
            node_dirty = 0
        else:
            node_dirty = 1

        # Find correct node entry in stats data
        # The following list comprehension should be guarenteed to return at
        # most one result
        nodes = [elem for elem in self.element.findall('Node') \
                 if elem.get('name') == client]
        nummatch = len(nodes)
        if nummatch == 0:
            # Create an entry for this node
            node = lxml.etree.SubElement(self.element, 'Node', name=client)
        elif nummatch == 1 and not node_dirty:
            # Delete old instance
            node = nodes[0]
            [node.remove(elem) for elem in node.findall('Statistics') \
             if self.isOlderThan24h(elem.get('time'))]
        elif nummatch == 1 and node_dirty:
            # Delete old dirty statistics entry
            node = nodes[0]
            [node.remove(elem) for elem in node.findall('Statistics') \
             if (elem.get('state') == 'dirty' \
                 and self.isOlderThan24h(elem.get('time')))]
        else:
            # Shouldn't be reached
            self.logger.error("Duplicate node entry for %s"%(client))

        # Set current time for stats
        newstat.set('time', asctime(localtime()))

        # Add statistic
        node.append(copy.copy(newstat))

        # Set dirty
        self.dirty = 1
        self.WriteBack(force=1)

    def isOlderThan24h(self, testTime):
        """Helper function to determine if <time> string is older than 24 hours."""
        now = time()
        utime = mktime(strptime(testTime))
        secondsPerDay = 60*60*24

        return (now-utime) > secondsPerDay


class Statistics(Bcfg2.Server.Plugin.ThreadedStatistics,
                 Bcfg2.Server.Plugin.PullSource):
    name = 'Statistics'
    deprecated = True

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.ThreadedStatistics.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.PullSource.__init__(self)
        fpath = "%s/etc/statistics.xml" % datastore
        self.data_file = StatisticsStore(fpath)

    def handle_statistic(self, metadata, data):
        self.data_file.updateStats(data, metadata.hostname)

    def FindCurrent(self, client):
        rt = self.data_file.element.xpath('//Node[@name="%s"]' % client)[0]
        maxtime = max([strptime(stat.get('time')) for stat \
                       in rt.findall('Statistics')])
        return [stat for stat in rt.findall('Statistics') \
                if strptime(stat.get('time')) == maxtime][0]

    def GetExtra(self, client):
        return [(entry.tag, entry.get('name')) for entry \
                in self.FindCurrent(client).xpath('.//Extra/*')]

    def GetCurrentEntry(self, client, e_type, e_name):
        curr = self.FindCurrent(client)
        entry = curr.xpath('.//Bad/%s[@name="%s"]' % (e_type, e_name))
        if not entry:
            raise Bcfg2.Server.Plugin.PluginExecutionError
        cfentry = entry[-1]

        owner = cfentry.get('current_owner', cfentry.get('owner'))
        group = cfentry.get('current_group', cfentry.get('group'))
        mode = cfentry.get('current_mode', cfentry.get('mode'))
        if cfentry.get('sensitive') in ['true', 'True']:
            raise Bcfg2.Server.Plugin.PluginExecutionError
        elif 'current_bfile' in cfentry.attrib:
            contents = b64decode(cfentry.get('current_bfile'))
        elif 'current_bdiff' in cfentry.attrib:
            diff = b64decode(cfentry.get('current_bdiff'))
            contents = '\n'.join(difflib.restore(diff.split('\n'), 1))
        else:
            contents = None

        return (owner, group, mode, contents)
