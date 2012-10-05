import os
import Bcfg2.Server.Plugin

class AclFile(Bcfg2.Server.Plugin.XMLFileBacked):
	""" representation of ACL config.xml """

	def __init__(self, filename, core=None):
		try:
			fam = core.fam
		except AttributeError:
			fam = None
		Bcfg2.Server.Plugin.XMLFileBacked.__init__(self, filename, fam=fam,
												   should_monitor=True)
		self.core = core
		self.ips = []

class Acl(Bcfg2.Server.Plugin.Plugin,
		  Bcfg2.Server.Plugin.Connector):
	""" allow connections to bcfg-server based on IP address """

	def __init__(self, core, datastore):
		Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
		Bcfg2.Server.Plugin.Connector.__init__(self)
		self.config = AclFile(os.path.join(self.data, 'config.xml'), core=core)
