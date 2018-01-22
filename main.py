import cgi
import urllib
import logging
import json
import os

from google.appengine.ext.webapp import template
from google.appengine.api import images
from google.appengine.api import users
from google.appengine.ext import ndb

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
    """Models a Guestbook entry with an author, content, photo, and date."""
    author = ndb.StringProperty()
    content = ndb.TextProperty()
    photo = ndb.BlobProperty()
    thumbnail = ndb.BlobProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)
    photo_datetime = ndb.StringProperty()
    photo_latitude = ndb.FloatProperty()
    photo_longitude = ndb.FloatProperty()


def guestbook_key(guestbook_name=None):
    """Constructs a Datastore key for a Guestbook entity with name."""
    return ndb.Key('Guestbook', guestbook_name or 'default_guestbook')


def is_in_whitelist(user):
    if user:
        if user.nickname() in white_list_users:
            return True
        for domain in user.nickname():
            if domain in user.nickname():
                return True
    return False


class Api(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if is_in_whitelist(user):
            self.response.headers['Content-Type'] = 'application/json'
            guestbook_name = self.request.get('guestbook_name')

            greetings = Greeting.query(
                ancestor=guestbook_key(guestbook_name)) \
                .order(-Greeting.date) \
                .fetch()

            return_array = []
            for greeting in greetings:
                return_obj = {
                    "author": greeting.author if greeting.author else "NA",
                    "photo": "/img?type=full&img_id=" + greeting.key.urlsafe(),
                    "thumbnail": "/img?type=thumbnail&img_id=" + greeting.key.urlsafe(),
                    "notes": cgi.escape(greeting.content),
                    "lat": greeting.photo_latitude,
                    "long": greeting.photo_longitude,
                    "photoDT": greeting.photo_datetime,
                    "eventDT": str(greeting.date)
                }
                return_array.append(return_obj)
            self.response.out.write(json.dumps(return_array))
        elif user and user.nickname() not in white_list_users:
            nickname = user.nickname()
            logout_url = users.create_logout_url('/')
            greeting = 'Welcome, {}, you are not on the whitelist, '.format(nickname)
            template_values = {
                        "message": greeting,
                        "button_msg": "sign out.",
                        "loginout_url": logout_url
                    }
            template = JINJA_ENVIRONMENT.get_template('empty_index.html')
            self.response.write(template.render(template_values))
        else:
            login_url = users.create_login_url('/')
            greeting = 'Welcome, please '
            template_values = {
                        "message": greeting,
                        "button_msg": "sign in.",
                        "loginout_url": login_url
                    }
            template = JINJA_ENVIRONMENT.get_template('empty_index.html')
            self.response.write(template.render(template_values))


class MainPage(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if is_in_whitelist(user):
            guestbook_name = self.request.get('guestbook_name')
            guestbook_name = "default_guestbook" if guestbook_name is None or len(guestbook_name) == 0 else guestbook_name
            update = False
            escaped_guestbook_name = None
            if user.nickname() in uploader_white_list_users:
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
        elif user and user.nickname() not in white_list_users:
            nickname = user.nickname()
            logout_url = users.create_logout_url('/')
            greeting = 'Welcome, {}, you are not on the whitelist, '.format(nickname)
            template_values = {
                        "message": greeting,
                        "button_msg": "sign out.",
                        "loginout_url": logout_url
                    }
            template = JINJA_ENVIRONMENT.get_template('empty_index.html')
            self.response.write(template.render(template_values))
        else:
            login_url = users.create_login_url('/')
            greeting = 'Welcome, please '
            template_values = {
                        "message": greeting,
                        "button_msg": "sign in.",
                        "loginout_url": login_url
                    }
            template = JINJA_ENVIRONMENT.get_template('empty_index.html')
            self.response.write(template.render(template_values))


# [START image_handler]
class Image(webapp2.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if is_in_whitelist(user):
            photo_type = self.request.get('type')
            greeting_key = ndb.Key(urlsafe=self.request.get('img_id'))
            greeting = greeting_key.get()
            if greeting.photo:
                self.response.headers['Content-Type'] = 'image/png'
                if photo_type == "thumbnail":
                    self.response.out.write(greeting.thumbnail)
                else:
                    self.response.out.write(greeting.photo)
            else:
                self.response.out.write('No image')
        elif user and user.nickname() not in white_list_users:
            nickname = user.nickname()
            logout_url = users.create_logout_url('/')
            greeting = 'Welcome, {}, you are not on the whitelist, '.format(nickname)
            template_values = {
                        "message": greeting,
                        "button_msg": "sign out.",
                        "loginout_url": logout_url
                    }
            template = JINJA_ENVIRONMENT.get_template('empty_index.html')
            self.response.write(template.render(template_values))
        else:
            login_url = users.create_login_url('/')
            greeting = 'Welcome, please '
            template_values = {
                        "message": greeting,
                        "button_msg": "sign in.",
                        "loginout_url": login_url
                    }
            template = JINJA_ENVIRONMENT.get_template('empty_index.html')
            self.response.write(template.render(template_values))
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
        user = users.get_current_user()
        if user and user.nickname() in uploader_white_list_users:
            guestbook_name = self.request.get('guestbook_name')
            greeting = Greeting(parent=guestbook_key(guestbook_name))

            if users.get_current_user():
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
        elif user and user.nickname() not in white_list_users:
            nickname = user.nickname()
            logout_url = users.create_logout_url('/')
            greeting = 'Welcome, {}, you are not on the whitelist, '.format(nickname)
            template_values = {
                        "message": greeting,
                        "button_msg": "sign out.",
                        "loginout_url": logout_url
                    }
            template = JINJA_ENVIRONMENT.get_template('empty_index.html')
            self.response.write(template.render(template_values))
        else:
            login_url = users.create_login_url('/')
            greeting = 'Welcome, please '
            template_values = {
                        "message": greeting,
                        "button_msg": "sign in.",
                        "loginout_url": login_url
                    }
            template = JINJA_ENVIRONMENT.get_template('empty_index.html')
            self.response.write(template.render(template_values))


app = webapp2.WSGIApplication([('/', MainPage),
                               ('/img', Image),
                               ('/sign', Guestbook),
                               ('/v1/api', Api)],
                              debug=True)
# [END all]
