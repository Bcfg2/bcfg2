#!/usr/bin/env python

class NodeConfigurationError(Exception):
    def __init__(self,node,etype):
        self.node=node
        self.etype=etype

    def __str__(self):
        return "NCE: %s:%s"%(self.node,self.etype)
