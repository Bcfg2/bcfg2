#!/usr/bin/env python

'''This is the Structure base class'''
__revision__ = '$Revision$'

class Structure(object):
    '''The Structure class is used to define patterns of data in host configurations
    Structure subtyped classes provide functions that group configurations into dependent
    and independent clauses'''
    __name__ = 'example'

    def __init__(self, core, datastore):
        '''Common structure setup'''
        object.__init__(self)
        self.data = "%s/%s" % (datastore, self.__name__)
        self.core = core
        self.__setup__()

    def __setup__(self):
        pass

    def Construct(self, metadata):
        '''Returns a list of configuration structure chunks for client'''
        return []

    
