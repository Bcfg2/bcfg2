"""This contains all Bcfg2 Client modules"""

__all__ = ["Frame", "Tools", "XML", "Client"]

import os
import sys
import select
from Bcfg2.Compat import input  # pylint: disable=W0622


def prompt(msg):
    """ Helper to give a yes/no prompt to the user.  Flushes input
    buffers, handles exceptions, etc.  Returns True if the user
    answers in the affirmative, False otherwise.

    :param msg: The message to show to the user.  The message is not
                altered in any way for display; i.e., it should
                contain "[y/N]" if desired, etc.
    :type msg: string
    :returns: bool - True if yes, False if no """
    while len(select.select([sys.stdin.fileno()], [], [], 0.0)[0]) > 0:
        os.read(sys.stdin.fileno(), 4096)
    try:
        ans = input(msg.encode(sys.stdout.encoding, 'replace'))
        return ans in ['y', 'Y']
    except EOFError:
        # python 2.4.3 on CentOS doesn't like ^C for some reason
        return False
    except:
        print("Error while reading input: %s" % sys.exc_info()[1])
        return False
