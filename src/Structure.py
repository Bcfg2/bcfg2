#!/usr/bin/env python
# $Id: $

class Structure(object):
    '''The Structure class is used to define patterns of data in host configurations
    Structure subtyped classes provide functions that group configurations into dependent
    and independent clauses'''

    def __init__(self, core, datastore):
        self.data = "%s/%s"%(datastore,self.__name__)
        self.core = core
        self.__setup__()

    def __setup__(self):
        pass

    def Construct(self, metadata, subset):
        '''Returns a list of configuration structure chunks for client'''
        return []

    
