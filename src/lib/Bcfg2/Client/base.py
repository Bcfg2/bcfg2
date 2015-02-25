"""This contains all Bcfg2 Client modules"""

import sys
import fnmatch

from Bcfg2.Utils import safe_input
from Bcfg2.Compat import any, all, cmp  # pylint: disable=redefined-builtin


def cmpent(ent1, ent2):
    """Sort entries."""
    if ent1.tag != ent2.tag:
        return cmp(ent1.tag, ent2.tag)
    else:
        return cmp(ent1.get('name'), ent2.get('name'))


def matches_entry(entryspec, entry):
    """ Determine if the Decisions-style entry specification matches
    the entry.  Both are tuples of (tag, name).  The entryspec can
    handle the wildcard * in either position. """
    if entryspec == entry:
        return True
    return all(fnmatch.fnmatch(entry[i], entryspec[i]) for i in [0, 1])


def matches_white_list(entry, whitelist):
    """ Return True if (<entry tag>, <entry name>) is in the given
    whitelist. """
    return any(matches_entry(we, (entry.tag, entry.get('name')))
               for we in whitelist)


def passes_black_list(entry, blacklist):
    """ Return True if (<entry tag>, <entry name>) is not in the given
    blacklist. """
    return not any(matches_entry(be, (entry.tag, entry.get('name')))
                   for be in blacklist)


def prompt(msg):
    """ Helper to give a yes/no prompt to the user.  Flushes input
    buffers, handles exceptions, etc.  Returns True if the user
    answers in the affirmative, False otherwise.

    :param msg: The message to show to the user.  The message is not
                altered in any way for display; i.e., it should
                contain "[y/N]" if desired, etc.
    :type msg: string
    :returns: bool - True if yes, False if no """
    try:
        ans = safe_input(msg)
        return ans in ['y', 'Y']
    except UnicodeEncodeError:
        ans = input(msg.encode('utf-8'))
        return ans in ['y', 'Y']
    except (EOFError, KeyboardInterrupt):
        # handle ^C
        raise SystemExit(1)
    except:  # pylint: disable=bare-except
        print("Error while reading input: %s" % sys.exc_info()[1])
        return False
