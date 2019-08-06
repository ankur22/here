from enum import Enum

from google.appengine.api import users

from emails import uploader_white_list_users
from emails import white_list_users
from emails import white_listed_domains


class Privileges(Enum):
    READ=1
    WRITE=2
    BLOCKED=4
    UNKNOWN=8
    ADMIN=16

    @classmethod
    def can_read(cls, privilege):
        return cls.is_blocked(privilege) is False and privilege & cls.READ != 0

    @classmethod
    def can_write(cls, privilege):
        return cls.is_blocked(privilege) is False and privilege & cls.WRITE != 0

    @classmethod
    def is_blocked(cls, privilege):
        return privilege & cls.BLOCKED != 0

    @classmethod
    def is_admin(cls, privilege):
        return privilege & cls.ADMIN != 0


def get_user_privileges():
    user = users.get_current_user()
    if user:
        if users.is_current_user_admin():
            return Privileges.READ | Privileges.WRITE | Privileges.ADMIN
        if user.nickname() in uploader_white_list_users:
            return Privileges.READ | Privileges.WRITE
        if user.nickname() in white_list_users:
            return Privileges.READ
        for domain in user.nickname():
            if domain in user.nickname():
                return Privileges.READ
        return Privileges.BLOCKED
    else:
        return Privileges.UNKNOWN

def get_nickname():
    return users.get_current_user().nickname()

def get_logout_url(url):
    return users.create_logout_url(url)

def get_login_url(url):
    return users.create_login_url('/')
