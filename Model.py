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

    def deleteImage(self, image):
        if str(image.img_id) in self.image_id_lst:
            print "size of blobkey before: " + str(len(self.image_id_lst))
            self.image_id_lst.remove(image.img_id)
            self.blob_key_lst.remove(image.blob_key)
            print "size of blobkey after: " + str(len(self.image_id_lst))
            key = image.put()
            print "get1: " + str(key.get())
            key.delete()
            print "get2: " + str(key.get())
            self.put()

    def deleteStream(self):
        key = self.put()
        key.delete()

# Subscription Data Model:
#   Each object indicates a subscription relationship between a user and a stream
#   Method Calls:
#       (x)addSubscription: calls when a user wants to subscribe a stream,
#       deleteSubscription: calls when a user wants to un-subscribe a stream
#                           or the stream has been removed by the creator.

class Subscription(ndb.Model):
    user_id = ndb.StringProperty()
    stream_id = ndb.StringProperty()
    subscribed_date = ndb.DateTimeProperty(auto_now_add=True)

    def deleteSubscription(self):
        key = self.put()
        key.delete()


