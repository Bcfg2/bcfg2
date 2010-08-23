import lxml.etree
import Bcfg2.Server.Plugin
import glob
import os
import socket

#manage boot symlinks
  #add statistics check to do build->boot mods

#map profiles: first array is not empty we replace the -p with a determined profile.
logger = Bcfg2.Server.Plugin.logger

class BBfile(Bcfg2.Server.Plugin.XMLFileBacked):
    """Class for bb files."""
    def Index(self):
        """Build data into an xml object."""

        try:
            self.data = lxml.etree.XML(self.data)
        except lxml.etree.XMLSyntaxError:
            Bcfg2.Server.Plugin.logger.error("Failed to parse %s" % self.name)
            return
        self.tftppath = self.data.get('tftp', '/tftpboot')
        self.macs = {}
        self.users = {}
        self.actions = {}
        self.bootlinks = []

        for node in self.data.findall('Node'):
            iface = node.find('Interface')
            if iface != None:
                mac = "01-%s" % (iface.get('mac'.replace(':','-').lower()))
                self.actions[node.get('name')] = node.get('action')
                self.bootlinks.append((mac, node.get('action')))
                try:
                    ip = socket.gethostbyname(node.get('name'))
                except:
                    logger.error("failed host resolution for %s" % node.get('name'))

                self.macs[node.get('name')] = (iface.get('mac'), ip)
            else:
                logger.error("%s" % lxml.etree.tostring(node))
            self.users[node.get('name')] = node.get('user',"").split(':')

    def enforce_bootlinks(self):
        for mac, target in self.bootlinks:
            path = self.tftppath + '/' + mac
            if not os.path.islink(path):
                logger.error("Boot file %s not a link" % path)
            if target != os.readlink(path):
                try:
                    os.unlink(path)
                    os.symlink(target, path)
                except:
                    logger.error("Failed to modify link %s" % path)

class BBDirectoryBacked(Bcfg2.Server.Plugin.DirectoryBacked):
    __child__ = BBfile


class BB(Bcfg2.Server.Plugin.Plugin,
         Bcfg2.Server.Plugin.Connector):
    """The BB plugin maps users to machines and metadata to machines."""
    name = 'BB'
    version = '$Revision$'
    deprecated = True

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.store = BBDirectoryBacked(self.data, core.fam)

    def get_additional_data(self, metadata):

        users = {}
        for user in self.store.entries['bb.xml'].users.get(metadata.hostname.split(".")[0], []):
            pubkeys = []
            for fname in glob.glob('/home/%s/.ssh/*.pub'%user):
                pubkeys.append(open(fname).read())

            users[user] = pubkeys

        return dict([('users', users),
                      ('macs', self.store.entries['bb.xml'].macs)])
