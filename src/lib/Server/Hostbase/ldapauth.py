import os
import ldap

"""Checks with LDAP (ActiveDirectory) to see if the current user is an LDAP(AD) user,
and returns a subset of the user's profile that is needed by Argonne/CIS to
to set user level privleges in Django"""


class LDAPAUTHError(Exception):
    """LDAPAUTHError is raised when somehting goes boom."""
    pass

class ldapauth(object):
    group_test = False
    check_member_of = os.environ['LDAP_CHECK_MBR_OF_GRP']
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

    def __init__(self,login,passwd=None):
        """get username (if using ldap as auth the
        apache env var REMOTE_USER should be used)
        from username get user profile from AD/LDAP
        """
        p = self.user_profile(login,passwd)
        if p[0] == 'success':
            #parse results
            parsed = self.parse_results(p[2])
            self.group_test = self.member_of()
                    
        else:
            raise LDAPAUTHError(p[2])

    def user_profile(self,login,passwd=None):
        ldap_login = "CN=%s" % login
        svc_acct = os.environ['LDAP_SVC_ACCT_NAME']
        svc_pass = os.environ['LDAP_SVC_ACCT_PASS']
        #svc_acct = 'CN=%s,DC=anl,DC=gov' % login
        #svc_pass = passwd

        svc_search_pth = os.environ['LDAP_SVC_SEARCH_PTH']
        
        try:
            conn = ldap.initialize(os.environ['LDAP_URI'])
            conn.bind(svc_acct,svc_pass,ldap.AUTH_SIMPLE)
            result_id = conn.search(svc_search_pth,
                                      ldap.SCOPE_SUBTREE,
                                      ldap_login,None)
            result_type,result_data = conn.result(result_id,0)
            return ('success','User profile found',result_data,)
        except ldap.LDAPError,e:
            #connection failed
            return ('error','LDAP connect failed',e,)

    def parse_results(self,user_obj):
        """Clean up the huge ugly object handed to us in the LDAP query"""
        #user_obj is a list formatted like this:
        #[('LDAP_DN',{user_dict},),]
        try:
            raw_obj = user_obj[0][1]
            self.memberOf = raw_obj['memberOf']
            self.sAMAccountName = raw_obj['sAMAccountName']
            self.distinguishedName = raw_obj['distinguishedName']
            self.telephoneNumber = raw_obj['telephoneNumber']
            self.title = raw_obj['title']
            self.department = raw_obj['department']
            self.mail = raw_obj['mail']
            self.badge_no = raw_obj['extensionAttribute1']
            return
        except KeyError, e:
            raise LDAPAUTHError("Portions of the LDAP User profile not present")
        
    def member_of(self):
        """See if this user is in our group that is allowed to login"""
        m = [g for g in self.memberOf if g == self.check_member_of]
        #print m
        if len(m) == 1:
            return True
        else:
            return False
