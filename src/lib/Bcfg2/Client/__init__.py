"""This contains all Bcfg2 Client modules"""

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
        ans = input(msg)
        return ans in ['y', 'Y']
    except EOFError:
        # handle ^C on rhel-based platforms
        raise SystemExit(1)
