from google.appengine.ext import ndb


class Image(ndb.Model):
    img_id = ndb.StringProperty()
    user_id = ndb.StringProperty()
    content = ndb.TextProperty()
    blob_key = ndb.BlobKeyProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)
    location = ndb.GeoPtProperty()

    @classmethod
    def get_image(self, img_id):
        image = Image.query(Image.img_id == img_id).fetch()
        #   return the stream if the stream list is not empty
        return image[0] if image else image


class Stream(ndb.Model):
    user_id = ndb.StringProperty()
    description = ndb.StringProperty()
    stream_name = ndb.StringProperty()
    stream_id = ndb.StringProperty()
    cover_url = ndb.StringProperty()
    views_cnt = ndb.IntegerProperty()   # added on 0929 for trends; this will get reset every hour
    total_views_cnt = ndb.IntegerProperty()     # added on 0929 for counting the views in total
    image_id_lst = ndb.StringProperty(repeated=True)
    blob_key_lst = ndb.BlobKeyProperty(repeated=True)
    viewsRecording = ndb.DateTimeProperty(repeated=True)
    last_add = ndb.DateTimeProperty(auto_now_add=True)

    @ndb.transactional(xg=True)
    def addImage(self, key, image):
        if image.img_id in self.image_id_lst:
            return
        image.put()
        self.blob_key_lst.insert(0, image.blob_key)
        # print "[Stream]addImage:: adding image (blob_key=", image.blob_key, ")"
        # print "[Stream]addImage:: new self.blob_ket_lst: ", self.blob_key_lst
        self.last_add = image.date
        self.image_id_lst.insert(0, image.img_id)
        self.put()

    def deleteImage(self, image):
        if str(image.img_id) in self.image_id_lst:
            # print "size of blobkey before: " + str(len(self.image_id_lst))
            self.image_id_lst.remove(image.img_id)
            self.blob_key_lst.remove(image.blob_key)
            # print "size of blobkey after: " + str(len(self.image_id_lst))
            key = image.put()
            key.delete()
            self.put()

    def deleteStream(self):
        key = self.put()
        key.delete()

    def increase_view_cnt(self):
        if self.views_cnt is None:
            self.views_cnt = 0
        if self.total_views_cnt is None:
            self.total_views_cnt = 0
        self.views_cnt += 1
        self.total_views_cnt += 1
        self.put()

    def reset_view_cnt(self):
        self.views_cnt = 0
        self.put()

    @classmethod
    def get_stream(self, stream_id):
        stream = Stream.query(Stream.stream_id == stream_id).fetch()
        #   return the stream if the stream list is not empty
        return stream[0] if stream else stream

    def dumpStream(self):
        return {k:v if v is None else (str(v) if not hasattr(v,'__iter__') else map(str,v))
                for k,v in self.to_dict().items()}


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


class ReportSendingRate(ndb.Model):
    user_email = ndb.StringProperty()
    sending_rate = ndb.IntegerProperty()

    def update_sending_rate(self, update_rate):
        self.sending_rate = update_rate
        self.put()
