
import json
import lxml.etree
import os
import Bcfg2.Server.Plugin

class OhaiCache(object):
    def __init__(self, dirname):
        self.dirname = dirname
        self.cache = dict()

    def __setitem__(self, item, value):
        self.cache[item] = json.loads(value)
        file("%s/%s.json" % (self.dirname, item), 'w').write(value)        

    def __getitem__(self, item):
        if item not in self.cache:
            try:
                data = open("%s/%s.json" % (self.dirname, item)).read()
            except:
                raise KeyError, item
            self.cache[item] = json.loads(data)
        return self.cache[item]

    def __iter__(self):
        data = self.cache.keys()
        data.extend([x[:-5] for x in os.listdir(self.dirname)])
        return data.__iter__()

class Ohai(Bcfg2.Server.Plugin.Plugin,
           Bcfg2.Server.Plugin.Probing,
           Bcfg2.Server.Plugin.Connector):
    name = 'Ohai'
    experimental = True

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Probing.__init__(self)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.probe = lxml.etree.Element('probe', name='Ohai', source='Ohai',
                                        interpreter='/bin/sh')
        self.probe.text = 'ohai'
        try:
            os.stat(self.data)
        except:
            self.make_path(self.data)
        self.cache = OhaiCache(self.data)

    def GetProbes(self, meta, force=False):
        return [self.probe]

    def ReceiveData(self, meta, datalist):
        self.cache[meta.hostname] = datalist[0].text

    def get_additional_data(self, meta):
        if meta.hostname in self.cache:
            return self.cache[meta.hostname]
        return dict()
