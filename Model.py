from google.appengine.ext import blobstore
from google.appengine.ext import ndb

class Image(ndb.Model):

    user_id = ndb.StringProperty()
    blob_key = ndb.BlobKeyProperty()
    content = ndb.TextProperty()
    avatar = ndb.BlobProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)




class Stream(ndb.Model):

    user_id = ndb.StringProperty()
    stream_name = ndb.StringProperty()
    cover_url = ndb.StringProperty()
    images = ndb.StringProperty(repeated=True)
    views = ndb.DateTimeProperty(repeated=True)
    last_add = ndb.DateTimeProperty()

    def addImage(self, image):
        if str(image.blob_key) in self.images:
            return
        image.put()
        self.images.insert(0,str(image.blob_key))
        self.last_add = image.create_date
        self.put()


