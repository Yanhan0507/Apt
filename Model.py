import uuid
from google.appengine.ext import ndb

class Image(ndb.Model):
    img_id = ndb.StringProperty()
    user_id = ndb.StringProperty()
    content = ndb.TextProperty()
    blob_key = ndb.BlobKeyProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)




class Stream(ndb.Model):

    user_id = ndb.StringProperty()
    stream_name = ndb.StringProperty()
    stream_id = ndb.StringProperty()
    cover_url = ndb.StringProperty()
    image_id_lst = ndb.StringProperty(repeated=True)
    blob_key_lst = ndb.BlobKeyProperty(repeated=True)
    viewsRecording = ndb.DateTimeProperty(repeated=True)
    last_add = ndb.DateTimeProperty(auto_now_add=True)

    def addImage(self, image):
        if str(image.img_id) in self.image_id_lst:
            return
        image.put()
        self.blob_key_lst.insert(0,image.blob_key)
        self.last_add = image.date
        self.image_id_lst.insert(0, image.img_id)
        self.put()


