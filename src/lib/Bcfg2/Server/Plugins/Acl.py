import os
import logging
import Bcfg2.Server.Plugin

class AclFile(Bcfg2.Server.Plugin.XMLFileBacked):
	""" representation of ACL config.xml """

	# 'name' error without this tag
	__identifier__ = None

	def __init__(self, filename, core=None):
		# create config.xml if missing
		if not os.path.exists(filename):
			LOGGER.warning("Acl: %s missing. "
						   "Creating empty one for you." % filename)
			open(filename, "w").write("<Acl></Acl>")

		try:
			fam = core.fam
		except AttributeError:
			fam = None

		Bcfg2.Server.Plugin.XMLFileBacked.__init__(self, filename, fam=fam,
												   should_monitor=True)
		self.core = core
		self.ips = []
		self.logger = logging.getLogger(self.__class__.__name__)
	
	def Index(self):
		Bcfg2.Server.Plugin.XMLFileBacked.Index(self)
		for entry in self.xdata.xpath('//IPs'):
			[self.ips.append(i.get('name')) for i in entry.findall('IP')]

class Acl(Bcfg2.Server.Plugin.Plugin,
		  Bcfg2.Server.Plugin.Connector):
	""" allow connections to bcfg-server based on IP address """

	def __init__(self, core, datastore):
		Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
		Bcfg2.Server.Plugin.Connector.__init__(self)
		self.config = AclFile(os.path.join(self.data, 'config.xml'), core=core)

