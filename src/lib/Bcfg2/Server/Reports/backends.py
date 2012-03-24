from django.contrib.auth.models import User
from nisauth import *


class NISBackend(object):

    def authenticate(self, username=None, password=None):
        try:
            print("start nis authenticate")
            n = nisauth(username, password)
            temp_pass = User.objects.make_random_password(100)
            nis_user = dict(username=username,
                            )

            user_session_obj = dict(email=username,
                                    first_name=None,
                                    last_name=None,
                                    uid=n.uid)
            user, created = User.objects.get_or_create(username=username)

            return user

        except NISAUTHError:
            e = sys.exc_info()[1]
            print(e)
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            e = sys.exc_info()[1]
            print(e)
            return None
