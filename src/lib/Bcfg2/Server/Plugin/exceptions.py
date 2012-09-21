""" Exceptions for Bcfg2 Server Plugins."""


class PluginInitError(Exception):
    """Error raised in cases of
    :class:`Bcfg2.Server.Plugin.base.Plugin` initialization errors."""
    pass


class PluginExecutionError(Exception):
    """Error raised in case of
    :class:`Bcfg2.Server.Plugin.base.Plugin` execution errors."""
    pass


class MetadataConsistencyError(Exception):
    """This error gets raised when metadata is internally
    inconsistent."""
    pass


class MetadataRuntimeError(Exception):
    """This error is raised when the metadata engine is called prior
    to reading enough data, or for other
    :class:`Bcfg2.Server.Plugin.interfaces.Metadata` errors."""
    pass


class ValidationError(Exception):
    """ Exception raised by
    :class:`Bcfg2.Server.Plugin.interfaces.StructureValidator` and
    :class:`Bcfg2.Server.Plugin.interfaces.GoalValidator` objects """


class SpecificityError(Exception):
    """ Thrown by :class:`Bcfg2.Server.Plugin.helpers.Specificity` in
    case of filename parse failure."""
    pass
