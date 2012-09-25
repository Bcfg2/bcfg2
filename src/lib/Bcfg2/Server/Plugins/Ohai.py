"""The Ohai plugin is used to detect information about the client
operating system using ohai
(http://wiki.opscode.com/display/chef/Ohai) """

import lxml.etree
import os
import Bcfg2.Server.Plugin

try:
    import json
except ImportError:
    import simplejson as json

PROBECODE = """#!/bin/sh

export PATH=$PATH:/sbin:/usr/sbin

if type ohai >& /dev/null; then
    ohai
else
    # an empty dict, so "'foo' in metadata.Ohai" tests succeed
    echo '{}'
fi
"""


class OhaiCache(object):
    """ Storage for Ohai output on the local filesystem so that the
    output can be used by bcfg2-info, etc. """
    def __init__(self, dirname):
        self.dirname = dirname
        self.cache = dict()

    def __setitem__(self, item, value):
        if value == None:
            # simply return if the client returned nothing
            return
        self.cache[item] = json.loads(value)
        open("%s/%s.json" % (self.dirname, item), 'w').write(value)

    def __getitem__(self, item):
        if item not in self.cache:
            try:
                data = open("%s/%s.json" % (self.dirname, item)).read()
            except:
                raise KeyError(item)
            self.cache[item] = json.loads(data)
        return self.cache[item]

    def __iter__(self):
        data = list(self.cache.keys())
        data.extend([x[:-5] for x in os.listdir(self.dirname)])
        return data.__iter__()


class Ohai(Bcfg2.Server.Plugin.Plugin,
           Bcfg2.Server.Plugin.Probing,
           Bcfg2.Server.Plugin.Connector):
    """The Ohai plugin is used to detect information
    about the client operating system.
    """
    name = 'Ohai'
    experimental = True

    def __init__(self, core, datastore):
        Bcfg2.Server.Plugin.Plugin.__init__(self, core, datastore)
        Bcfg2.Server.Plugin.Probing.__init__(self)
        Bcfg2.Server.Plugin.Connector.__init__(self)
        self.probe = lxml.etree.Element('probe', name='Ohai', source='Ohai',
                                        interpreter='/bin/sh')
        self.probe.text = PROBECODE
        try:
            os.stat(self.data)
        except OSError:
            os.makedirs(self.data)
        self.cache = OhaiCache(self.data)

    def GetProbes(self, _):
        return [self.probe]

    def ReceiveData(self, meta, datalist):
        self.cache[meta.hostname] = datalist[0].text

    def get_additional_data(self, meta):
        if meta.hostname in self.cache:
            return self.cache[meta.hostname]
        return dict()
