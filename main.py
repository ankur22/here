import cgi
import urllib
import logging
import json
import os

from google.appengine.ext.webapp import template
from google.appengine.api import images

import jinja2
import webapp2

import dao
from mem_cache import MemCacheHandler
import user
from user import Privileges

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


def return_not_on_whitelist_screen(instance):
    nickname = user.get_nickname()
    logout_url = user.get_logout_url(url)
    message = 'Welcome, {}, you are not on the whitelist, '.format(nickname)
    template_values = {
                "message": message,
                "button_msg": "sign out.",
                "loginout_url": logout_url
            }
    template = JINJA_ENVIRONMENT.get_template('empty_index.html')
    instance.set_status(401)
    instance.response.write(template.render(template_values))


def return_login_screen(instance):
    login_url = user.get_login_url('/')
    message = 'Welcome, please '
    template_values = {
                "message": message,
                "button_msg": "sign in.",
                "loginout_url": login_url
            }
    template = JINJA_ENVIRONMENT.get_template('empty_index.html')
    instance.response.write(template.render(template_values))


class UpdateCache(webapp2.RequestHandler):

    def get(self):
        privilege = user.get_user_privileges()
        if Privileges.is_admin(privilege):
            self.response.headers['Content-Type'] = 'application/json'
            guestbook_name = self.request.get('guestbook_name')

            MemCacheHandler.update_events_cache(guestbook_name)
            self.response.out.write('Event cache updated')
        else:
            return_login_screen(self)


class Api(webapp2.RequestHandler):

    def get(self):
        privilege = user.get_user_privileges()
        if Privileges.can_read(privilege):
            self.response.headers['Content-Type'] = 'application/json'
            guestbook_name = self.request.get('guestbook_name')

            greetings = MemCacheHandler.get_all_events(guestbook_name)
            self.response.out.write(json.dumps(greetings))
        elif Privileges.is_blocked(privilege):
            return_not_on_whitelist_screen(self)
        else:
            return_login_screen(self)


class MainPage(webapp2.RequestHandler):
    def get(self):
        privilege = user.get_user_privileges()
        if Privileges.can_read(privilege):
            guestbook_name = self.request.get('guestbook_name')
            guestbook_name = "default_guestbook" if guestbook_name is None or len(guestbook_name) == 0 else guestbook_name
            update = False
            escaped_guestbook_name = None
            if Privileges.can_write(privilege):
                update = True
                guestbook_name = urllib.urlencode({'guestbook_name': guestbook_name})
                escaped_guestbook_name = cgi.escape(guestbook_name)
            logout_url = user.get_logout_url('/')
            template_values = {
                        "update": update,
                        "guestbook_name": guestbook_name,
                        "escaped_guestbook_name": escaped_guestbook_name,
                        "logout_url": logout_url
                    }
            template = JINJA_ENVIRONMENT.get_template('index.html')
            self.response.write(template.render(template_values))
        elif Privileges.is_blocked(privilege):
            return_not_on_whitelist_screen(self)
        else:
            return_login_screen(self)


class Image(webapp2.RequestHandler):

    def get(self):
        privilege = user.get_user_privileges()
        if Privileges.can_read(privilege):
            photo_type = self.request.get('type')
            [thumbnail, photo] = MemCacheHandler.get_images_and_update_image_cache(self.request.get('img_id'))
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
            return_not_on_whitelist_screen(self)
        else:
            return_login_screen(self)


class Guestbook(webapp2.RequestHandler):

    def rotate_and_get_metadata(self, uploaded_image):
        img = images.Image(image_data=uploaded_image)
        img.rotate(0)
        img.set_correct_orientation(1)
        photo = img.execute_transforms(parse_source_metadata=True, output_encoding=images.JPEG)
        logging.info(img.get_original_metadata())
        return [photo, img.get_original_metadata()]

    def post(self):
        privilege = user.get_user_privileges()
        if Privileges.can_write(privilege):
            guestbook_name = self.request.get('guestbook_name')
            greeting = dao.create_greeting(guestbook_name)
            greeting.author = user.get_nickname()
            greeting.content = self.request.get('content')

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
                    greeting.photo = images.resize(photo, 768, 768)
                    greeting.thumbnail = images.resize(photo, 128, 128)
                    greeting.photo_latitude = metadata['GPSLatitude']
                    greeting.photo_longitude = metadata['GPSLongitude']
                    greeting.photo_datetime = metadata['DateTime'] if 'DateTime' in metadata else ""
                    greeting.put()

                    MemCacheHandler.update_events_cache(guestbook_name)

                self.redirect('/?' + urllib.urlencode(
                    {'guestbook_name': guestbook_name}))
        elif Privileges.is_blocked(privilege):
            return_not_on_whitelist_screen(self)
        else:
            return_login_screen(self)


app = webapp2.WSGIApplication([('/', MainPage),
                               ('/img', Image),
                               ('/sign', Guestbook),
                               ('/v1/api', Api),
                               ('/v1/cache/update', UpdateCache)],
                              debug=True)
