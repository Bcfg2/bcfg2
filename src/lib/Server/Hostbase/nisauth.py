"""Checks with NIS to see if the current user is in the support group"""
import os
import crypt, nis
from Bcfg2.Server.Hostbase.settings import AUTHORIZED_GROUP


class NISAUTHError(Exception):
    """NISAUTHError is raised when somehting goes boom."""
    pass

class nisauth(object):
    group_test = False
#    check_member_of = os.environ['LDAP_CHECK_MBR_OF_GRP']
    samAcctName = None
    distinguishedName = None
    sAMAccountName = None
    telephoneNumber = None
    title = None
    memberOf = None
    department = None #this will be a list
    mail = None
    extensionAttribute1 = None #badgenumber
    badge_no = None
    uid = None

    def __init__(self,login,passwd=None):
        """get user profile from NIS"""
        try:
            p = nis.match(login, 'passwd.byname').split(":")
        except:
            raise NISAUTHError('username')
        # check user password using crypt and 2 character salt from passwd file
        if p[1] == crypt.crypt(passwd, p[1][:2]):
            # check to see if user is in valid support groups
            # will have to include these groups in a settings file eventually
            if not login in nis.match(AUTHORIZED_GROUP, 'group.byname').split(':')[-1].split(',') and p[3] != nis.match(AUTHORIZED_GROUP, 'group.byname').split(':')[2]:
                raise NISAUTHError('group')
            self.uid = p[2]
        else:
            raise NISAUTHError('password')
