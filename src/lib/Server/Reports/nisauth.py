import crypt
import nis
from Bcfg2.Server.Reports.settings import AUTHORIZED_GROUP

"""Checks with NIS to see if the current user is in the support group"""

__revision__ = "$Revision: $"


class NISAUTHError(Exception):
    """NISAUTHError is raised when somehting goes boom."""
    pass


class nisauth(object):
    group_test = False
    samAcctName = None
    distinguishedName = None
    sAMAccountName = None
    telephoneNumber = None
    title = None
    memberOf = None
    department = None  # this will be a list
    mail = None
    extensionAttribute1 = None  # badgenumber
    badge_no = None
    uid = None

    def __init__(self, login, passwd=None):
        """get user profile from NIS"""
        try:
            p = nis.match(login, 'passwd.byname').split(":")
            print(p)
        except:
            raise NISAUTHError('username')
        # check user password using crypt and 2 character salt from passwd file
        if p[1] == crypt.crypt(passwd, p[1][:2]):
            # check to see if user is in valid support groups
            # will have to include these groups in a settings file eventually
            if not login in nis.match(AUTHORIZED_GROUP,
                                      'group.byname').split(':')[-1].split(','):
                raise NISAUTHError('group')
            self.uid = p[2]
            print(self.uid)
        else:
            raise NISAUTHError('password')
