import webapp2, json
import logging  #for loggings
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext import blobstore
from Model import Image, Stream, Subscription, ReportSendingRate
import uuid
import urllib
from google.appengine.ext import ndb

#   import the constants
from Constants import *

__author__ = 'ChenguangLiu'


# Main Service Handler class


class ServiceHandler(webapp2.RequestHandler):
    def respond(self, separators=(',', ':'), **response):
        if KEYWORD_ERROR in response and response[KEYWORD_ERROR]:
            #   record the error msg
            logging.error("Web Service Error: " + response[KEYWORD_ERROR])
        elif KEYWORD_STATUS in response:
            #   record the debugging status
            logging.debug("Web Service Debugging Information: " + response[KEYWORD_STATUS])

        if IDENTIFIER_JSON_MSG in self.request.headers.get('Accept'):
            self.response.headers['Content-Type'] = IDENTIFIER_JSON_MSG

        return self.response.write(json.dumps(response, separators=separators))


#   /ws/stream/view
#   return: idx_lst, blob_key_lst, image_id_lst
class ViewStreamService(ServiceHandler):
    def post(self):
        req_json = json.loads(self.request.body)
        stream_id = req_json[IDENTIFIER_STREAM_ID]
        req_idx_lst = req_json[IDENTIFIER_IMG_IDX_REQ_LIST].split(',')
        print 'ViewStreamService >> get stream id: ', stream_id, ', image_req_idx_lst:', req_idx_lst
        stream_obj = Stream()
        stream = stream_obj.get_stream(stream_id)

        # check if the stream exists
        if not stream:
            return self.respond(error="ViewStreamService >> Requested stream id %s does not exist." % stream_id)

        # now start retrieving images
        image_id_lst = []  # saving img ids
        image_res_idx_lst = []  # saving img indexes. There might be inconsistency between the requested list and this one
        blob_key_lst = []

        if not req_idx_lst:
            #   if the index list turns out to be empty
            return self.respond(error="ViewStreamService >> index list is empty")

        for idx in req_idx_lst:
            if not idx:
                break
            idx = int(idx)
            if idx >= len(stream.image_id_lst):
                continue
            image_id_lst.append(stream.image_id_lst[idx])
            blob_key_lst.append(str(stream.blob_key_lst[idx]))
            image_res_idx_lst.append(idx)

        #   increase view count
        stream.increase_view_cnt()

        self.respond(stream_owner=stream.user_id, image_res_idx_lst=image_res_idx_lst, blob_key_lst=blob_key_lst,
                     image_id_lst=image_id_lst, stream_name=stream.stream_name, stream_description=stream.description,
                     status="Retrieved image indexes %r from stream %r" % (image_id_lst, stream_id))


#   /ws/stream/create
class CreateStreamService(ServiceHandler):
    def post(self):
        req_json = json.loads(self.request.body)
        user_id = req_json[IDENTIFIER_CURRENT_USER_ID]
        stream_name = req_json[IDENTIFIER_STREAM_NAME]
        stream_id = uuid.uuid4()
        cover_url = req_json[IDENTIFIER_COVER_URL]
        description = req_json[IDENTIFIER_STREAM_DESC]

        new_stream = Stream(parent=ndb.Key('Account', user_id),
                            user_id=user_id,
                            stream_id=str(stream_id),
                            stream_name=stream_name,
                            views_cnt=0,
                            total_views_cnt=0,
                            cover_url=cover_url,
                            description=description)
        new_stream.put()
        print 'Successfully created new stream:', str(stream_id)
        self.respond(stream_id=str(stream_id), status="Success")


#   /ws/stream/subscribe
#   post method return whether the user is subscribed to the stream
#   get method is for subscribe/un-subscribe (#   required fields: stream_id; (user exists in the request).)
#           - implemented in SubscriptionHandler
class SubscriptionService(ServiceHandler):
    def post(self):
        req_json = json.loads(self.request.body)
        stream_id = req_json[IDENTIFIER_STREAM_ID]
        current_user_id = req_json[IDENTIFIER_CURRENT_USER_ID]
        print "SubscriptionService >> checking subscription stream_id: " + stream_id + ", user_id:" + current_user_id
        sub_query = Subscription.query(Subscription.user_id == current_user_id, Subscription.stream_id == stream_id).fetch()
        if len(sub_query) != 0:
            # subscription exists
            subscribe_option = "Unsubscribe"
            subscribe_url = "/subscribe?stream_id="+stream_id+"&subscribe_bool=false"\
                            + "&"+IDENTIFIER_CURRENT_USER_ID+"=" + current_user_id
        else:
            # subscription doesn't exist
            subscribe_option = "Subscribe"
            subscribe_url = "/subscribe?stream_id="+stream_id+"&subscribe_bool=true"\
                            + "&"+IDENTIFIER_CURRENT_USER_ID+"=" + current_user_id
        self.respond(subscribe_option=subscribe_option, subscribe_url=subscribe_url, status="Success")


# Blobstore related services
class ViewImageService(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        blob_key = self.request.get(KEYWORD_BLOBKEY)
        if not blobstore.get(blob_key):
            self.error(404)
        else:
            self.send_blob(blob_key)


# Service Address: /ws/stream/upload_image
# Request Fields: IDENTIFIER_CURRENT_USER_ID, IDENTIFIER_STREAM_ID, IDENTIFIER_STREAM_DESC
class UploadImageService(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        user_id = self.request.get(IDENTIFIER_CURRENT_USER_ID)
        stream_id = self.request.get(IDENTIFIER_STREAM_ID)
        description = self.request.get(IDENTIFIER_STREAM_DESC)

        print 'UploadImageService >> get upload image request ', len(self.get_uploads())

        for upload in self.get_uploads():
            #get the blob store object
            # upload = self.get_uploads()[0]
            image_id = uuid.uuid4()
            print "UploadImageService >> Upload new image with blob_key: " + str(upload.key())
            user_image = Image(user_id=user_id,
                               img_id=str(image_id),
                               content=description,
                               blob_key=upload.key())
            # stream_lst = Stream.query(Stream.user_id == user_id, Stream.stream_id == stream_id).fetch()
            # cur_stream = stream_lst[0]
            current_stream = Stream().get_stream(stream_id)
            if current_stream:
                print "UploadImageService >> stream id:", stream_id, ", added image id: ", str(image_id)

                current_stream.addImage(key=user_image.img_id, image=user_image)
                print "UploadImageService >> blob_key_lst after adding: ", current_stream.blob_key_lst
            else:
                print "UploadImageService >> Fail to add user photo ", user_image, "to stream ", stream_id


# Service for querying user's streams or his subscribed streams
# Service Address: /ws/stream/query
# Request Fields: IDENTIFIER_CURRENT_USER_ID(str), IDENTIFIER_CHECK_SUBSCRIPTION(boolean)