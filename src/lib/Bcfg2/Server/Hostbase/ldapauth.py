"""
Checks with LDAP (ActiveDirectory) to see if the current user is an LDAP(AD)
user, and returns a subset of the user's profile that is needed by Argonne/CIS
to set user level privleges in Django
"""

import os
import ldap


class LDAPAUTHError(Exception):
    """LDAPAUTHError is raised when somehting goes boom."""
    pass


class ldapauth(object):
    group_test = False
    check_member_of = os.environ['LDAP_CHECK_MBR_OF_GRP']
    securitylevel = 0
    distinguishedName = None
    sAMAccountName = None
    telephoneNumber = None
    title = None
    memberOf = None
    department = None  # this will be a list
    mail = None
    extensionAttribute1 = None  # badgenumber
    badge_no = None

    def __init__(self, login, passwd):
        """get username (if using ldap as auth the
        apache env var REMOTE_USER should be used)
        from username get user profile from AD/LDAP
        """
        #p = self.user_profile(login,passwd)
        d = self.user_dn(login)  # success, distname
        print(d[1])
        if d[0] == 'success':
            pass
            p = self.user_bind(d[1], passwd)
            if p[0] == 'success':
                #parse results
                parsed = self.parse_results(p[2])
                print(self.department)
                self.group_test = self.member_of()
                securitylevel = self.security_level()
                print("ACCESS LEVEL: " + str(securitylevel))
            else:
                raise LDAPAUTHError(p[2])
        else:
            raise LDAPAUTHError(p[2])

    def user_profile(self, login, passwd=None):
        """NOT USED RIGHT NOW"""
        ldap_login = "CN=%s" % login
        svc_acct = os.environ['LDAP_SVC_ACCT_NAME']
        svc_pass = os.environ['LDAP_SVC_ACCT_PASS']
        #svc_acct = 'CN=%s,DC=anl,DC=gov' % login
        #svc_pass = passwd

        search_pth = os.environ['LDAP_SEARCH_PTH']

        try:
            conn = ldap.initialize(os.environ['LDAP_URI'])
            conn.bind(svc_acct, svc_pass, ldap.AUTH_SIMPLE)
            result_id = conn.search(search_pth,
                                    ldap.SCOPE_SUBTREE,
                                    ldap_login,
                                    None)
            result_type, result_data = conn.result(result_id, 0)
            return ('success', 'User profile found', result_data,)
        except ldap.LDAPError:
            e = sys.exc_info()[1]
            #connection failed
            return ('error', 'LDAP connect failed', e,)

    def user_bind(self, distinguishedName, passwd):
        """Binds to LDAP Server"""
        search_pth = os.environ['LDAP_SEARCH_PTH']
        try:
            conn = ldap.initialize(os.environ['LDAP_URI'])
            conn.bind(distinguishedName, passwd, ldap.AUTH_SIMPLE)
            cn = distinguishedName.split(",")
            result_id = conn.search(search_pth,
                                    ldap.SCOPE_SUBTREE,
                                    cn[0],
                                    None)
            result_type, result_data = conn.result(result_id, 0)
            return ('success', 'User profile found', result_data,)
        except ldap.LDAPError:
            e = sys.exc_info()[1]
            #connection failed
            return ('error', 'LDAP connect failed', e,)

    def user_dn(self, cn):
        """Uses Service Account to get distinguishedName"""
        ldap_login = "CN=%s" % cn
        svc_acct = os.environ['LDAP_SVC_ACCT_NAME']
        svc_pass = os.environ['LDAP_SVC_ACCT_PASS']
        search_pth = os.environ['LDAP_SEARCH_PTH']

        try:
            conn = ldap.initialize(os.environ['LDAP_URI'])
            conn.bind(svc_acct, svc_pass, ldap.AUTH_SIMPLE)
            result_id = conn.search(search_pth,
                                    ldap.SCOPE_SUBTREE,
                                    ldap_login,
                                    None)
            result_type, result_data = conn.result(result_id, 0)
            raw_obj = result_data[0][1]
            distinguishedName = raw_obj['distinguishedName']
            return ('success', distinguishedName[0],)
        except ldap.LDAPError:
            e = sys.exc_info()[1]
            #connection failed
            return ('error', 'LDAP connect failed', e,)

    def parse_results(self, user_obj):
        """Clean up the huge ugly object handed to us in the LDAP query"""
        #user_obj is a list formatted like this:
        #[('LDAP_DN',{user_dict},),]
        try:
            raw_obj = user_obj[0][1]
            self.memberOf = raw_obj['memberOf']
            self.sAMAccountName = raw_obj['sAMAccountName'][0]
            self.distinguishedName = raw_obj['distinguishedName'][0]
            self.telephoneNumber = raw_obj['telephoneNumber'][0]
            self.title = raw_obj['title'][0]
            self.department = raw_obj['department'][0]
            self.mail = raw_obj['mail'][0]
            self.badge_no = raw_obj['extensionAttribute1'][0]
            self.email = raw_obj['extensionAttribute2'][0]
            display_name = raw_obj['displayName'][0].split(",")
            self.name_f = raw_obj['givenName'][0]
            self.name_l = display_name[0]
            self.is_staff = False
            self.is_superuser = False

            return
        except KeyError:
            e = sys.exc_info()[1]
            raise LDAPAUTHError("Portions of the LDAP User profile not present")

    def member_of(self):
        """See if this user is in our group that is allowed to login"""
        m = [g for g in self.memberOf if g == self.check_member_of]
        if len(m) == 1:
            return True
        else:
            return False

    def security_level(self):
        level = self.securitylevel

        user = os.environ['LDAP_GROUP_USER']
        m = [g for g in self.memberOf if g == user]
        if len(m) == 1:
            if level < 1:
                level = 1

        cspr = os.environ['LDAP_GROUP_SECURITY_LOW']
        m = [g for g in self.memberOf if g == cspr]
        if len(m) == 1:
            if level < 2:
                level = 2

        cspo = os.environ['LDAP_GROUP_SECURITY_HIGH']
        m = [g for g in self.memberOf if g == cspo]
        if len(m) == 1:
            if level < 3:
                level = 3

        admin = os.environ['LDAP_GROUP_ADMIN']
        m = [g for g in self.memberOf if g == admin]
        if len(m) == 1:
            if level < 4:
                level = 4

        return level
