""" Provides access-control lists for server connections """

import Bcfg2.Server.Plugin

class Acl(Bcfg2.Server.Plugin.PrioDir):
	name = "Acl"

	def __init__(self, core, datastore):
