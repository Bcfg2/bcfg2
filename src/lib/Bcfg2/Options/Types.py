""" :mod:`Bcfg2.Options` provides a number of useful types for use
with the :class:`Bcfg2.Options.Option` constructor. """

import os
import re
import pwd
import grp

_COMMA_SPLIT_RE = re.compile(r'\s*,\s*')


def path(value):
    """ A generic path.  ``~`` will be expanded with
    :func:`os.path.expanduser` and the absolute resulting path will be
    used.  This does *not* ensure that the path exists. """
    return os.path.abspath(os.path.expanduser(value))


def comma_list(value):
    """ Split a comma-delimited list, with optional whitespace around
    the commas."""
    return _COMMA_SPLIT_RE.split(value)


def colon_list(value):
    """ Split a colon-delimited list.  Whitespace is not allowed
    around the colons. """
    return value.split(':')


def comma_dict(value):
    """ Split an option string on commas, optionally surrounded by
    whitespace, and split the resulting items again on equals signs,
    returning a dict """
    result = dict()
    if value:
        items = comma_list(value)
        for item in items:
            if '=' in item:
                key, value = item.split(r'=', 1)
                try:
                    result[key] = bool(value)
                except ValueError:
                    try:
                        result[key] = int(value)
                    except ValueError:
                        result[key] = value
            else:
                result[item] = True
    return result


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


_bytes_multipliers = dict(k=1,
                          m=2,
                          g=3,
                          t=4)
_suffixes = "".join(_bytes_multipliers.keys()).lower()
_suffixes += _suffixes.upper()
_bytes_re = re.compile(r'(?P<value>\d+)(?P<multiplier>[%s])?' % _suffixes)


def size(value):
    """ Given a number of bytes in a human-readable format (e.g.,
    '512m', '2g'), get the absolute number of bytes as an integer.
    """
    if value == -1:
        return value
    mat = _bytes_re.match(value)
    if not mat:
        raise ValueError("Not a valid size", value)
    rvalue = int(mat.group("value"))
    mult = mat.group("multiplier")
    if mult:
        return rvalue * (1024 ** _bytes_multipliers[mult.lower()])
    else:
        return rvalue
