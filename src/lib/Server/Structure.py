'''This is the Structure base class'''
__revision__ = '$Revision$'

class StructureError(Exception):
    '''Structure runtime error used to inform upper layers of internal generator failure'''
    pass

class StructureInitError(Exception):
    '''Constructor time error that allows the upper layer to proceed in the face of
    structure initialization failures'''
    pass

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
        metadata.image # pylint hack
        return []

    def GetDependencies(self, metadata):
        '''Get a list of dependencies for structures returned by Construct'''
        metadata.image
        return []
