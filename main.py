import cgi
import urllib
import logging
import json
import os
from enum import Enum

from google.appengine.ext.webapp import template
from google.appengine.api import images
from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.api import memcache

import jinja2
import webapp2

from emails import uploader_white_list_users
from emails import white_list_users
from emails import white_listed_domains

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class Greeting(ndb.Model):
    """Models a diary entry with an author, content, photo, date, etc."""
    author = ndb.StringProperty()
    content = ndb.TextProperty()
    photo = ndb.BlobProperty()
    thumbnail = ndb.BlobProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)
    photo_datetime = ndb.StringProperty()
    photo_latitude = ndb.FloatProperty()
    photo_longitude = ndb.FloatProperty()


def guestbook_key(guestbook_name=None):
    """Constructs a Datastore key for a diary entity with name."""
    return ndb.Key('Guestbook', guestbook_name or 'default_guestbook')


class Privileges(Enum):
    READ=1
    WRITE=2
    BLOCKED=4
    UNKNOWN=8

    @classmethod
    def can_read(cls, privilege):
        return cls.is_blocked(privilege) is False and privilege & cls.READ != 0

    @classmethod
    def can_write(cls, privilege):
        return cls.is_blocked(privilege) is False and privilege & cls.WRITE != 0

    @classmethod
    def is_blocked(cls, privilege):
        return privilege & cls.BLOCKED != 0


def get_user_privileges():
    user = users.get_current_user()
    if user:
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


def return_not_on_whitelist(self):
    nickname = users.get_current_user().nickname()
    logout_url = users.create_logout_url('/')
    message = 'Welcome, {}, you are not on the whitelist, '.format(nickname)
    template_values = {
                "message": message,
                "button_msg": "sign out.",
                "loginout_url": logout_url
            }
    template = JINJA_ENVIRONMENT.get_template('empty_index.html')
    self.set_status(401)
    self.response.write(template.render(template_values))


def return_login_screen(self):
    login_url = users.create_login_url('/')
    message = 'Welcome, please '
    template_values = {
                "message": message,
                "button_msg": "sign in.",
                "loginout_url": login_url
            }
    template = JINJA_ENVIRONMENT.get_template('empty_index.html')
    self.response.write(template.render(template_values))


def thumbnail_cache_name(img_id):
    return "%s-thumbnail" % img_id

def photo_cache_name(img_id):
    return "%s-photo" % img_id


class Api(webapp2.RequestHandler):

    def __get_from_cache(self):
        page_name = "page0"
        pages = []
        page = {}

        while page is not None:
            page = memcache.get(page_name)
            if page is not None:
                pages.append(page)
                page_name = page["next_page_name"]

        return pages

    def __convert_to_response_ready_obj(self, greeting):
        return {
            "author": greeting.author if greeting.author else "NA",
            "photo": "/img?type=full&img_id=" + greeting.key.urlsafe(),
            "thumbnail": "/img?type=thumbnail&img_id=" + greeting.key.urlsafe(),
            "notes": cgi.escape(greeting.content),
            "lat": greeting.photo_latitude,
            "long": greeting.photo_longitude,
            "photoDT": greeting.photo_datetime,
            "eventDT": str(greeting.date)
        }

    def __get_from_datastore(self, guestbook_name, offset, limit):
        return Greeting.query(
            ancestor=guestbook_key(guestbook_name)) \
            .order(-Greeting.date) \
            .fetch(offset=offset, limit=limit)

    def __get_all(self, guestbook_name):
        pages = self.__get_from_cache()
        count = len(pages)
        elms_in_page = 5
        greetings = ["na"]

        while greetings is not None and len(greetings) > 0:
            count_in_last_page = len(pages[count - 1]["data"]) if count > 0 else 0
            offset = ((count - 1) * elms_in_page) + count_in_last_page if count > 0 else count_in_last_page
            limit = elms_in_page - count_in_last_page if count_in_last_page != elms_in_page else elms_in_page

            greetings = self.__get_from_datastore(guestbook_name, offset, limit)

            if greetings is not None and len(greetings) > 0:
                data = []
                for greeting in greetings:
                    obj = self.__convert_to_response_ready_obj(greeting)
                    data.append(obj)

                    # Only add new values for images to memcache
                    memcache.add(thumbnail_cache_name(greeting.key.urlsafe()), greeting.thumbnail)
                    memcache.add(photo_cache_name(greeting.key.urlsafe()), greeting.photo)

                # Update existing memcache value
                if len(pages) > 0 and len(pages[count - 1]["data"]) < elms_in_page:
                    pages[count - 1]["data"].extend(data)
                    memcache.replace(pages[count - 1]["page_name"], pages[count - 1])
                else: # Add new memcache value
                    page = {
                        "page_name": "page{}".format(count),
                        "next_page_name": "page{}".format(count + 1),
                        "data": data
                    }
                    count = count + 1
                    pages.append(page)
                    memcache.add(page["page_name"], page)

        rtn_val = []
        for page in pages:
            rtn_val.extend(page["data"])

        return rtn_val


    def get(self):
        privilege = get_user_privileges()
        if Privileges.can_read(privilege):
            self.response.headers['Content-Type'] = 'application/json'
            guestbook_name = self.request.get('guestbook_name')

            greetings = self.__get_all(guestbook_name)
            self.response.out.write(json.dumps(greetings))
        elif Privileges.is_blocked(privilege):
            return_not_on_whitelist(self)
        else:
            return_login_screen(self)


class MainPage(webapp2.RequestHandler):
    def get(self):
        privilege = get_user_privileges()
        if Privileges.can_read(privilege):
            guestbook_name = self.request.get('guestbook_name')
            guestbook_name = "default_guestbook" if guestbook_name is None or len(guestbook_name) == 0 else guestbook_name
            update = False
            escaped_guestbook_name = None
            if Privileges.can_write(privilege):
                update = True
                guestbook_name = urllib.urlencode({'guestbook_name': guestbook_name})
                escaped_guestbook_name = cgi.escape(guestbook_name)
            logout_url = users.create_logout_url('/')
            template_values = {
                        "update": update,
                        "guestbook_name": guestbook_name,
                        "escaped_guestbook_name": escaped_guestbook_name,
                        "logout_url": logout_url
                    }
            template = JINJA_ENVIRONMENT.get_template('index.html')
            self.response.write(template.render(template_values))
        elif Privileges.is_blocked(privilege):
            return_not_on_whitelist(self)
        else:
            return_login_screen(self)


# [START image_handler]
class Image(webapp2.RequestHandler):

    def __get_images(self, img_id):
        cached_thumbnail = memcache.get(thumbnail_cache_name(img_id))
        cached_photo = memcache.get(photo_cache_name(img_id))
        if cached_thumbnail is None or cached_photo is None:
            greeting_key = ndb.Key(urlsafe=img_id)
            greeting = greeting_key.get()
            if greeting.photo:
                # Only add new values for images to memcache
                memcache.add(thumbnail_cache_name(img_id), greeting.thumbnail)
                memcache.add(photo_cache_name(img_id), greeting.photo)
                return [greeting.thumbnail, greeting.photo]
            else:
                return [None, None]
        else:
            return [cached_thumbnail, cached_photo]

    def get(self):
        privilege = get_user_privileges()
        if Privileges.can_read(privilege):
            photo_type = self.request.get('type')
            [thumbnail, photo] = self.__get_images(self.request.get('img_id'))
            if thumbnail is not None and photo is not None:
                self.response.headers['Content-Type'] = 'image/png'
                if photo_type == "thumbnail":
                    self.response.out.write(thumbnail)
                else:
                    self.response.out.write(photo)
            else:
                self.set_status(404)
                self.response.out.write('No image')
        elif Privileges.is_blocked(privilege):
            return_not_on_whitelist(self)
        else:
            return_login_screen(self)
# [END image_handler]


# [START sign_handler]
class Guestbook(webapp2.RequestHandler):

    def rotate_and_get_metadata(self, uploaded_image):
        img = images.Image(image_data=uploaded_image)
        img.rotate(0)
        img.set_correct_orientation(1)
        photo = img.execute_transforms(parse_source_metadata=True, output_encoding=images.JPEG)
        logging.info(img.get_original_metadata())
        return [photo, img.get_original_metadata()]

    def post(self):
        privilege = get_user_privileges()
        if Privileges.can_write(privilege):
            guestbook_name = self.request.get('guestbook_name')
            greeting = Greeting(parent=guestbook_key(guestbook_name))
            greeting.author = users.get_current_user().nickname()
            greeting.content = self.request.get('content')

            # [START sign_handler_1]
            photo = self.request.get('img')
            if photo is None or len(photo) == 0:
                greeting = 'No photo supplied.'
                template_values = {
                            "message": greeting,
                            "button_msg": "Try again",
                            "loginout_url": "/"
                        }
                template = JINJA_ENVIRONMENT.get_template('empty_index.html')
                self.response.write(template.render(template_values))
                self.response.set_status(400)
            else:
                [photo, metadata] = self.rotate_and_get_metadata(photo)
                # [END sign_handler_1]

                if 'GPSLatitude' not in metadata or 'GPSLongitude' not in metadata:
                    greeting = 'No GPS coordinates in the image provided.'
                    template_values = {
                                "message": greeting,
                                "button_msg": "Try again",
                                "loginout_url": "/"
                            }
                    template = JINJA_ENVIRONMENT.get_template('empty_index.html')
                    self.response.write(template.render(template_values))
                    self.response.set_status(400)
                else:
                # [START sign_handler_2]
                    greeting.photo = images.resize(photo, 768, 768)
                    greeting.thumbnail = images.resize(photo, 128, 128)
                    greeting.photo_latitude = metadata['GPSLatitude']
                    greeting.photo_longitude = metadata['GPSLongitude']
                    greeting.photo_datetime = metadata['DateTime'] if 'DateTime' in metadata else ""
                    greeting.put()
                # [END sign_handler_1]

                self.redirect('/?' + urllib.urlencode(
                    {'guestbook_name': guestbook_name}))
        elif Privileges.is_blocked(privilege):
            return_not_on_whitelist(self)
        else:
            return_login_screen(self)


app = webapp2.WSGIApplication([('/', MainPage),
                               ('/img', Image),
                               ('/sign', Guestbook),
                               ('/v1/api', Api)],
                              debug=True)
# [END all]
