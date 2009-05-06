
import hashlib
import logging
import lxml.etree
import select
import socket
import threading
import time
import xmlrpclib

from Bcfg2.Component import Component, automatic, exposed, locking
import Bcfg2.Server.Core

logger = logging.getLogger('server')

def critical_error(operation):
    '''Log and err, traceback and return an xmlrpc fault to client'''
    logger.error(operation, exc_info=1)
    raise xmlrpclib.Fault(7, "Critical unexpected failure: %s" % (operation))

class SetupError(Exception):
    '''Used when the server cant be setup'''
    pass

class bcfg2_server(Component,
                   Bcfg2.Server.Core.Core):
    '''XML RPC interfaces for the server core'''
    name = 'bcfg2-server'
    implementation = 'bcfg2-server'
    
    def __init__(self, setup):
        Component.__init__(self)
        Bcfg2.Server.Core.Core.__init__(self, setup['repo'], setup['plugins'], 
                                        setup['password'], 
                                        setup['encoding'], setup['filemonitor'])
        self.ca = setup['ca']
        self.fam_thread = threading.Thread(target=self._file_monitor_thread)
        self.fam_thread.start()

    def _file_monitor_thread(self):
        famfd = self.fam.fileno()
        while True:
            try:
                if famfd:
                    rsockinfo = select.select([famfd], [], [])
                else:
                    while not self.fam.pending():
                        time.sleep(15)
                self.fam.handle_event_set(self.lock)
            except:
                continue

    @exposed
    def GetProbes(self, address):
        '''Fetch probes for a particular client'''
        resp = lxml.etree.Element('probes')
        try:
            name = self.metadata.resolve_client(address)
            meta = self.build_metadata(name)
            
            for plugin in [p for p in list(self.plugins.values()) \
                           if isinstance(p, Bcfg2.Server.Plugin.Probing)]:
                for probe in plugin.GetProbes(meta):
                    resp.append(probe)
            return lxml.etree.tostring(resp, encoding='UTF-8',
                                       xml_declaration=True)
        except Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError:
            warning = 'Client metadata resolution error for %s; check server log' % address[0]
            self.logger.warning(warning)
            raise xmlrpclib.Fault(6, warning)
        except:
            critical_error("error determining client probes")

    @exposed
    def RecvProbeData(self, address, probedata):
        '''Receive probe data from clients'''
        try:
            name = self.metadata.resolve_client(address)
            meta = self.build_metadata(name)
        except Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError:
            warning = 'metadata consistency error'
            self.logger.warning(warning)
            raise xmlrpclib.Fault(6, warning)
        # clear dynamic groups
        self.metadata.cgroups[meta.hostname] = []
        try:
            xpdata = lxml.etree.XML(probedata)
        except:
            self.logger.error("Failed to parse probe data from client %s" % \
                              (address[0]))
            return False

        sources = []
        [sources.append(data.get('source')) for data in xpdata
         if data.get('source') not in sources]
        for source in sources:
            if source not in self.plugins:
                self.logger.warning("Failed to locate plugin %s" % (source))
                continue
            dl = [data for data in xpdata if data.get('source') == source]
            try:
                self.plugins[source].ReceiveData(meta, dl)
            except:
                logger.error("Failed to process probe data from client %s" % \
                             (address[0]), exc_info=1)
        return True

    @exposed
    def AssertProfile(self, address, profile):
        '''Set profile for a client'''
        try:
            client = self.metadata.resolve_client(address)
            self.metadata.set_profile(client, profile, address)
        except (Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError,
                Bcfg2.Server.Plugins.Metadata.MetadataRuntimeError):
            warning = 'metadata consistency error'
            self.logger.warning(warning)
            raise xmlrpclib.Fault(6, warning)
        return True

    @exposed
    def GetConfig(self, address, checksum=False):
        '''Build config for a client'''
        try:
            client = self.metadata.resolve_client(address)
            config = self.BuildConfiguration(client)
            if checksum:
                for cfile in config.findall('.//ConfigFile'):
                    if cfile.text != None:
                        csum = hashlib.md5()
                        csum.update(cfile.text)
                        cfile.set('checksum', csum.hexdigest())
                        cfile.text = None
            return lxml.etree.tostring(config, encoding='UTF-8',
                                       xml_declaration=True)
        except Bcfg2.Server.Plugins.Metadata.MetadataConsistencyError:
            self.logger.warning("Metadata consistency failure for %s" % (address))
            raise xmlrpclib.Fault(6, "Metadata consistency failure")

    @exposed
    def RecvStats(self, address, stats):
        '''Act on statistics upload'''
        sdata = lxml.etree.XML(stats)
        client = self.metadata.resolve_client(address)        
        self.process_statistics(client, sdata)
        return "<ok/>"

    def authenticate(self, cert, user, password, address):
        if self.ca:
            acert = cert
        else:
            # no ca, so no cert validation can be done
            acert = None
        return self.metadata.AuthenticateConnection(acert, user, password, address)

    @exposed
    def GetDecisionList(self, address, mode):
        client = self.metadata.resolve_client(address)
        meta = self.build_metadata(client)
        return self.GetDecisions(meta, mode)
