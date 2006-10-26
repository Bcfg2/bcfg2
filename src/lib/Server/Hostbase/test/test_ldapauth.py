import os,sys
import harness

from Hostbase.ldapauth import *

def test_it():
    l = ldapauth(os.environ['LDAP_SVC_ACCT_NAME'],
                 os.environ['LDAP_SVC_ACCT_PASS'])

    assert l.department == 'foo'
