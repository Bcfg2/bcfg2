#!/usr/bin/env python
# $Id$

class NodeConfigurationError(Exception):
    def __init__(self,node,etype):
        self.node=node
        self.etype=etype

    def __str__(self):
        return "NCE: %s:%s"%(self.node,self.etype)

class GeneratorError(Exception):
    pass

class PublishError(Exception):
    pass

class CfgFileException(Exception):
    def __init__(self,op,filename):
        self.operation=op
        self.filename=filename
        
    def __str__(self):
        return "%s : %s"%(`self.operation`, `self.filename`)
