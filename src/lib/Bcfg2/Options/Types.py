""" :mod:`Bcfg2.Options` provides a number of useful types for use
with the :class:`Bcfg2.Options.Option` constructor. """

import os
import re
from Bcfg2.Compat import literal_eval, pwd, grp

_COMMA_SPLIT_RE = re.compile(r'\s*,\s*')


def path(value):
    """ A generic path.  ``~`` will be expanded with
    :func:`os.path.expanduser` and the absolute resulting path will be
    used.  This does *not* ensure that the path exists. """
    return os.path.abspath(os.path.expanduser(value))


def comma_list(value):
    """ Split a comma-delimited list, with optional whitespace around
    the commas."""
    if value == '':
        return []
    return _COMMA_SPLIT_RE.split(value)


def colon_list(value):
    """ Split a colon-delimited list.  Whitespace is not allowed
    around the colons. """
    if value == '':
        return []
    return value.split(':')


def literal_dict(value):
    """ literally evaluate the option in order to allow for arbitrarily nested
    dictionaries """
    return literal_eval(value)


def anchored_regex_list(value):
    """ Split an option string on whitespace and compile each element as
    an anchored regex """
    try:
        return [re.compile('^' + x + '$') for x in re.split(r'\s+', value)]
    except re.error:
        raise ValueError("Not a list of regexes", value)


def octal(value):
    """ Given an octal string, get an integer representation. """
    return int(value, 8)


def username(value):
    """ Given a username or numeric UID, get a numeric UID.  The user
    must exist."""
    try:
        return int(value)
    except ValueError:
        return int(pwd.getpwnam(value)[2])


def groupname(value):
    """ Given a group name or numeric GID, get a numeric GID.  The
    user must exist."""
    try:
        return int(value)
    except ValueError:
        return int(grp.getgrnam(value)[2])


def timeout(value):
    """ Convert the value into a float or None. """
    if value is None:
        return value
    rv = float(value)  # pass ValueError up the stack
    if rv <= 0:
        return None
    return rv


# pylint: disable=C0103
_bytes_multipliers = dict(k=1,
                          m=2,
                          g=3,
                          t=4)
_suffixes = "".join(_bytes_multipliers.keys()).lower()
_suffixes += _suffixes.upper()
_bytes_re = re.compile(r'(?P<value>\d+)(?P<multiplier>[%s])?' % _suffixes)
# pylint: enable=C0103


def size(value):
    """ Given a number of bytes in a human-readable format (e.g.,
    '512m', '2g'), get the absolute number of bytes as an integer.
    """
    mat = _bytes_re.match(value)
    if not mat:
        raise ValueError("Not a valid size", value)
    rvalue = int(mat.group("value"))
    mult = mat.group("multiplier")
    if mult:
        return rvalue * (1024 ** _bytes_multipliers[mult.lower()])
    else:
        return rvalue
