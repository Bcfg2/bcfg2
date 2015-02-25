""" Bcfg2.Server.FileMonitor provides the support for monitoring
files.  The FAM acts as a dispatcher for events: An event is detected
on a file (e.g., the file content is changed), and then that event is
dispatched to the ``HandleEvent`` method of an object that knows how
to handle the event.  Consequently,
:func:`Bcfg2.Server.FileMonitor.base.FileMonitor.AddMonitor` takes two
arguments: the path to monitor, and the object that handles events
detected on that event.

``HandleEvent`` is called with a single argument, the
:class:`Bcfg2.Server.FileMonitor.Event` object to be handled.

Assumptions
-----------

The FAM API Bcfg2 uses is based on the API of SGI's `File Alteration
Monitor <http://oss.sgi.com/projects/fam/>`_ (also called "FAM").
Consequently, a few assumptions apply:

* When a file or directory is monitored for changes, we call that a
  "monitor"; other backends my use the term "watch," but for
  consistency we will use "monitor."
* Monitors can be set on files or directories.
* A monitor set on a directory monitors all files within that
  directory, non-recursively.  If the object that requested the
  monitor wishes to monitor recursively, it must implement that
  itself.
* Setting a monitor immediately produces "exists" and "endExist"
  events for the monitored file or directory and all files or
  directories contained within it (non-recursively).
* An event on a file or directory that is monitored directly yields
  the full path to the file or directory.
* An event on a file or directory that is *only* contained within a
  monitored directory yields the relative path to the file or
  directory within the monitored parent.  It is the responsibility of
  the handler to reconstruct full paths as necessary.
* Each monitor that is set must have a unique ID that identifies it,
  in order to make it possible to reconstruct full paths as
  necessary.  This ID will be stored in
  :attr:`Bcfg2.Server.FileMonitor.FileMonitor.handles`.  It may be any
  hashable value; some FAM backends use monotonically increasing
  integers, while others use the path to the monitor.

Base Classes
------------
"""

import Bcfg2.Options

#: A module-level FAM object that all plugins, etc., can use.  This
#: should not be used directly, but retrieved via :func:`get_fam`.
_FAM = None


def get_fam():
    """ Get a
    :class:`Bcfg2.Server.FileMonitor.FileMonitor` object.  If
    :attr:`_FAM` has not been populated, then a new default
    FileMonitor will be created.

    :returns: :class:`Bcfg2.Server.FileMonitor.FileMonitor`
    """
    global _FAM  # pylint: disable=global-statement
    if _FAM is None:
        _FAM = Bcfg2.Options.setup.filemonitor()
    return _FAM


#: A dict of all available FAM backends.  Keys are the human-readable
#: names of the backends, which are used in bcfg2.conf to select a
#: backend; values are the backend classes.  In addition, the
#: ``default`` key will be set to the best FAM backend as determined
#: by :attr:`Bcfg2.Server.FileMonitor.FileMonitor.__priority__`
_AVAILABLE = dict()


def get_available():
    """Get a mapping of available FileMonitor backend classes."""
    if not _AVAILABLE:
        # TODO: loading the monitor drivers should be automatic
        from Bcfg2.Server.FileMonitor.Pseudo import Pseudo
        _AVAILABLE['pseudo'] = Pseudo

        try:
            from Bcfg2.Server.FileMonitor.Gamin import Gamin
            _AVAILABLE['gamin'] = Gamin
        except ImportError:
            pass

        try:
            from Bcfg2.Server.FileMonitor.Inotify import Inotify
            _AVAILABLE['inotify'] = Inotify
        except ImportError:
            pass

        for fdrv in reversed(sorted(_AVAILABLE.keys(),
                                    key=lambda k: _AVAILABLE[k].__priority__)):
            if fdrv in _AVAILABLE:
                _AVAILABLE['default'] = _AVAILABLE[fdrv]
                break
    return _AVAILABLE
