#!/usr/bin/env python

from binascii import b2a_base64
from string import join

class ConfigFile(object):
    format="<ConfigFile name='%s' owner='%s' group='%s' perms='%s' encoding='%s'>%s</ConfigFile>"
    def __init__(self,name,owner,group,perms,content,encoding='ascii'):
        self.name=name
        self.owner=owner
        self.group=group
        self.perms=perms
        self.content=content
        self.encoding=encoding
        if encoding == 'base64':
            self.xcontent=b2a_base64(content)
        else:
            self.xcontent=self.content
        
    def toxml(self):
        return self.format%(self.name,self.owner,self.group,self.perms,self.encoding,self.xcontent)

class Service(object):
    format = '''<Service name='%s' type='%s' status='%s' scope='%s'/>'''

    def __init__(self,name,stype,status,scope):
        self.name = name
        self.type = stype
        self.status = status
        self.scope = scope

    def toxml(self):
        return self.format%(self.name,self.type,self.status,self.scope)

class Package(object):
    format = '''<Package name='%s' type='%s' url='%s'/>'''

    def __init__(self, name, t, url):
        self.name = name
        self.type = t
        self.url = url

    def toxml(self):
        return self.format%(self.name, self.type, self.url)

class Clause(list):
    format = '''<%s name='%s'>%%s</%s>'''
    
    def __init__(self, t, name, data=None):
        list.__init__(self)
        self.type = t
        self.name = name
        if data:
            self.extend(data)

    def toxml(self):
        r = self.format%(self.type,self.name,self.type)
        children = map(lambda x:x.toxml(), self)
        return r%(join(children,''))
