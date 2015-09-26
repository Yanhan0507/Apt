import uuid
from google.appengine.ext import ndb

class Image(ndb.Model):
    ImageId = ndb.StringProperty()
    user_id = ndb.StringProperty()
    content = ndb.TextProperty()
    blob_key = ndb.BlobKeyProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)




class Stream(ndb.Model):

    user_id = ndb.StringProperty()
    stream_name = ndb.StringProperty()
    stream_id = ndb.StringProperty()
    cover_url = ndb.StringProperty()
    images = ndb.StringProperty(repeated=True)
    viewsRecording = ndb.DateTimeProperty(repeated=True)
    last_add = ndb.DateTimeProperty(auto_now_add=True)

    def addImage(self, image):
        if str(image.blob_key) in self.images:
            return
        image.put()
        self.images.insert(0,str(image.blob_key))
        self.last_add = image.date
        self.put()


