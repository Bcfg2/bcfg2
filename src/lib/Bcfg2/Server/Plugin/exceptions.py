""" Exceptions for Bcfg2 Server Plugins."""

class PluginInitError(Exception):
    """Error raised in cases of :class:`Bcfg2.Server.Plugin.Plugin`
    initialization errors."""
    pass


class PluginExecutionError(Exception):
    """Error raised in case of :class:`Bcfg2.Server.Plugin.Plugin`
    execution errors."""
    pass


class MetadataConsistencyError(Exception):
    """This error gets raised when metadata is internally inconsistent."""
    pass


class MetadataRuntimeError(Exception):
    """This error is raised when the metadata engine is called prior
    to reading enough data, or for other
    :class:`Bcfg2.Server.Plugin.Metadata` errors. """
    pass


class ValidationError(Exception):
    """ Exception raised by
    :class:`Bcfg2.Server.Plugin.StructureValidator` and
    :class:`Bcfg2.Server.Plugin.GoalValidator` objects """


class SpecificityError(Exception):
    """ Thrown by :class:`Bcfg2.Server.Plugin.Specificity` in case of
    filename parse failure."""
    pass
