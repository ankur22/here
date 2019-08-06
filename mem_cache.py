import cgi

from google.appengine.api import memcache

import dao


class MemCacheHandler():

    @classmethod
    def __thumbnail_cache_name(cls, img_id):
        return "%s-thumbnail" % img_id

    @classmethod
    def __photo_cache_name(cls, img_id):
        return "%s-photo" % img_id

    @classmethod
    def __get_page_name(cls, guestbookname, count):
        return "page{}{}".format(guestbookname, count)

    @classmethod
    def __get_from_cache(cls, guestbookname):
        page_name = cls.__get_page_name(guestbookname, 0)
        pages = []
        page = {}

        while page is not None:
            page = cls.get(page_name)
            if page is not None:
                pages.append(page)
                page_name = page["next_page_name"]

        return pages

    @classmethod
    def __convert_to_response_ready_obj(cls, greeting):
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

    @classmethod
    def update_events_cache(cls, guestbook_name):
        pages = cls.__get_from_cache(guestbook_name)
        count = len(pages)
        elms_in_page = 200
        greetings = ["na"]

        while greetings is not None and len(greetings) > 0:
            count_in_last_page = len(pages[count - 1]["data"]) if count > 0 else 0
            offset = ((count - 1) * elms_in_page) + count_in_last_page if count > 0 else count_in_last_page
            limit = elms_in_page - count_in_last_page if count_in_last_page != elms_in_page else elms_in_page

            greetings = dao.get_events_from_datastore(guestbook_name, offset, limit)

            if greetings is not None and len(greetings) > 0:
                data = []
                for greeting in greetings:
                    obj = cls.__convert_to_response_ready_obj(greeting)
                    data.append(obj)

                    # Only add new values for images to memcache
                    cls.add(cls.__thumbnail_cache_name(greeting.key.urlsafe()), greeting.thumbnail)
                    cls.add(cls.__photo_cache_name(greeting.key.urlsafe()), greeting.photo)

                # Update existing memcache value
                if len(pages) > 0 and len(pages[count - 1]["data"]) < elms_in_page:
                    pages[count - 1]["data"].extend(data)
                    memcache.replace(pages[count - 1]["page_name"], pages[count - 1])
                else: # Add new memcache value
                    page = {
                        "page_name": cls.__get_page_name(guestbook_name, count),
                        "next_page_name": cls.__get_page_name(guestbook_name, count + 1),
                        "data": data
                    }
                    count = count + 1
                    pages.append(page)
                    cls.add(page["page_name"], page)

    @classmethod
    def get_all_events(cls, guestbook_name):
        pages = cls.__get_from_cache(guestbook_name)
        rtn_val = []
        for page in pages:
            rtn_val.extend(page["data"])
        return rtn_val

    @classmethod
    def get_images_and_update_image_cache(cls, img_id):
        cached_thumbnail = cls.get(cls.__thumbnail_cache_name(img_id))
        cached_photo = cls.get(cls.__photo_cache_name(img_id))
        if cached_thumbnail is None or cached_photo is None:
            greeting_key = dao.get_key_for_img_id(img_id)
            greeting = greeting_key.get()
            if greeting.photo:
                # Only add new values for images to memcache
                cls.add(cls.__thumbnail_cache_name(img_id), greeting.thumbnail)
                cls.add(cls.__photo_cache_name(img_id), greeting.photo)
                return [greeting.thumbnail, greeting.photo]
            else:
                return [None, None]
        else:
            return [cached_thumbnail, cached_photo]

    @classmethod
    def get(cls, key):
        return memcache.get(key)

    @classmethod
    def add(cls, key, value):
        return memcache.add(key, value)
