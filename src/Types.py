#!/usr/bin/env python

from binascii import b2a_base64

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
        
    def XMLSerialize(self):
        return self.format%(self.name,self.owner,self.group,self.perms,self.encoding,self.xcontent)


