from google.appengine.ext import ndb

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

def create_greeting(guestbook_name):
    return Greeting(parent=guestbook_key(guestbook_name))

def get_events_from_datastore(guestbook_name, offset, limit):
    return Greeting.query(
        ancestor=guestbook_key(guestbook_name)) \
        .order(-Greeting.date) \
        .fetch(offset=offset, limit=limit)
