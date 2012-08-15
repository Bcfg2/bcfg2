from django.contrib.auth.models import User
#from ldapauth import *
from nisauth import *

## class LDAPBackend(object):

##     def authenticate(self,username=None,password=None):
##         try:

##             l = ldapauth(username,password)
##             temp_pass = User.objects.make_random_password(100)
##             ldap_user = dict(username=l.sAMAccountName,
##                              )
##             user_session_obj = dict(
##                 email=l.email,
##                 first_name=l.name_f,
##                 last_name=l.name_l,
##                 uid=l.badge_no
##                 )
##             #fixme: need to add this user session obj to session
##             user,created = User.objects.get_or_create(username=username)
##             return user

##         except LDAPAUTHError,e:
##             return None

##     def get_user(self,user_id):
##         try:
##             return User.objects.get(pk=user_id)
##         except User.DoesNotExist, e:
##             return None


class NISBackend(object):

    def authenticate(self, username=None, password=None):
        try:
            n = nisauth(username, password)
            temp_pass = User.objects.make_random_password(100)
            nis_user = dict(username=username,
                            )

            user_session_obj = dict(
                email = username + "@mcs.anl.gov",
                first_name = None,
                last_name = None,
                uid = n.uid
                )
            user, created = User.objects.get_or_create(username=username)

            return user

        except NISAUTHError:
            e = sys.exc_info()[1]
            return None


    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            e = sys.exc_info()[1]
            return None
