import webapp2, json
import logging  #for loggings
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext import blobstore
from Model import Image, Stream, Subscription, ReportSendingRate
import uuid
import random
from datetime import datetime
import urllib
from google.appengine.ext import ndb
from google.appengine.api.images import get_serving_url

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
        img_req_page = req_json[IDENTIFIER_IMG_REQ_PAGE]
        print 'ViewStreamService >> get stream id: ', stream_id, ', img_req_page:', img_req_page
        stream_obj = Stream()
        stream = stream_obj.get_stream(stream_id)

        # check if the stream exists
        if not stream:
            return self.respond(error="ViewStreamService >> Requested stream id %s does not exist." % stream_id)

        # now start retrieving images
        image_id_lst = []  # saving img ids
        image_res_idx_lst = []  # saving img indexes. There might be inconsistency between the requested list and this one
        blob_key_lst = []

        if not img_req_page:
            #   if the index list turns out to be empty
            return self.respond(error="ViewStreamService >> page index is empty")

        img_req_page = int(img_req_page)

        idx_lst = range(img_req_page*3, (img_req_page+1)*3, 1)

        for idx in idx_lst:
            if idx >= len(stream.image_id_lst):
                continue
            image_id_lst.append(stream.image_id_lst[idx])
            blob_key_lst.append(str(stream.blob_key_lst[idx]))
            image_res_idx_lst.append(idx)

        #   increase view count
        stream.increase_view_cnt()

        # next/prev page indexes
        if (img_req_page+1)*3 < len(stream.image_id_lst):
            next_pg_idx = img_req_page+1
        else:
            next_pg_idx = -1
        if img_req_page > 0:
            prev_pg_idx = img_req_page-1
        else:
            prev_pg_idx = -1

        self.respond(stream_owner=stream.user_id, image_res_idx_lst=image_res_idx_lst, blob_key_lst=blob_key_lst,
                     image_id_lst=image_id_lst, stream_name=stream.stream_name, stream_description=stream.description,
                     next_page_idx=next_pg_idx, prev_page_idx=prev_pg_idx,
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
        self.respond(subscribe_option=subscribe_option, subscribe_url=subscribe_url, status="success")


# Blobstore related services
# ViewImageService
class ViewImageService(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self):
        blob_key = self.request.get(KEYWORD_BLOBKEY)
        if not blobstore.get(blob_key):
            self.error(404)
        else:
            self.send_blob(blob_key)


# RemoveImageService
# Service Address: /ws/stream/remove_image
# Request Fields: IDENTIFIER_CURRENT_USER_ID, IDENTIFIER_STREAM_ID, IDENTIFIER_IMAGEID
class RemoveImageService(ServiceHandler):
    def post(self):
        req_json = json.loads(self.request.body)
        stream_id = req_json[IDENTIFIER_STREAM_ID]
        current_user_id = req_json[IDENTIFIER_CURRENT_USER_ID]
        photo_key = req_json[IDENTIFIER_PHOTO_KEY]

        response = {}
        stream = Stream.get_stream(stream_id)

        if not (stream_id and current_user_id and photo_key and stream):
            response['error'] = "Failed to find photo_key (" + photo_key + ") for user (" + current_user_id \
                                + ") under stream(" + stream_id+")."
            self.respond(**response)
        elif stream.user_id != current_user_id:
            response['error'] = "Failed to remove image user (" + current_user_id \
                                + ") is not the owner of stream(" + stream_id+")."
            self.respond(**response)
        else:
            stream.deleteImage(photo_key)
            self.respond(status="success")


# UploadImageService
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

            # Generate a random location - Phase II requirement
            rand_loc = ndb.GeoPt(random.uniform(-90, 90), random.uniform(0, 90))

            user_image = Image(user_id=user_id,
                               img_id=str(image_id),
                               content=description,
                               blob_key=upload.key(),
                               location=rand_loc)
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
class StreamQueryService(ServiceHandler):
    def post(self):
        req_json = json.loads(self.request.body)
        user_id = req_json[IDENTIFIER_CURRENT_USER_ID]
        is_check_subscription = req_json[IDENTIFIER_CHECK_SUBSCRIPTION]
        if not is_check_subscription:
            print 'StreamQueryService >> checking all streams created by user[', user_id, ']'
            user_streams_list = ndb.Query(ancestor=ndb.Key('Account', user_id)).fetch()
            sorted_streams_list = sorted(user_streams_list, key=lambda stream: stream.last_add, reverse=True)
            sid_list = []
            for stream in sorted_streams_list:
                sid_list.append(stream.stream_id)

            dumpablelist = [Stream.get_stream(stream_id).dumpStream()
                            for stream_id in sid_list]

            self.respond(user_streams_list=dumpablelist, status="success")

        else:
            print 'StreamQueryService >> checking all streams subscribed by user[', user_id, ']'
            subscribed_list = Subscription.query(Subscription.user_id == user_id).fetch()
            subscribed_stream_ids = []
            for subscribed_item in subscribed_list:
                sub_stream = Stream.query(Stream.stream_id == subscribed_item.stream_id).fetch()
                if len(sub_stream) != 0:
                    subscribed_stream_ids.append(sub_stream[0].stream_id)

            dumpablelist = [Stream.get_stream(stream_id).dumpStream()
                            for stream_id in subscribed_stream_ids]

            self.respond(user_sub_streams_list=dumpablelist, status="success")


# Service for getting a list of images with GeoLocations, and content(img divs)
# Service Address: /ws/stream/marker_query
# Request Fields: IDENTIFIER_STREAM_ID
class MarkersQueryService(ServiceHandler):
    def get(self):

        # req_json = json.loads(self.request.body)
        # stream_id = req_json[IDENTIFIER_STREAM_ID]

        stream_id = self.request.get(IDENTIFIER_STREAM_ID)

        #date_format:
        # query_begin_date = req_json['query_begin_date']
        # query_end_date = req_json['query_end_date']

        query_begin_date = self.request.get(QUERY_BEGIN_DATE)
        query_end_date = self.request.get(QUERY_END_DATE)

        begin_date = datetime.strptime(query_begin_date, '%Y-%m-%dT%H:%M:%S.%fZ')
        end_date = datetime.strptime(query_end_date, '%Y-%m-%dT%H:%M:%S.%fZ')

        stream = Stream.get_stream(stream_id)
        response = {}
        markers_lst = list()
        if not stream:
            response['error'] = "Failed to find stream(" + stream_id+")."
            self.respond(**response)
        else:
            for image_id in stream.image_id_lst:
                image = Image.get_image(image_id)
                if begin_date <= image.date <= end_date:
                    content = '<img src="'+get_serving_url(image.blob_key, size=100)+'">'
                    marker = {"latitude": image.location.lat, "longitude": image.location.lon, "content":content}
                    # marker = {KEYWORD_MARKER_LOC: image.location,
                    #           KEYWORD_MARKER_CONTENT: "<img src=\"" + get_serving_url(image.blob_key, size=100)+"\"\\>"}
                    markers_lst.append(marker)
            self.respond(markers=markers_lst, status="success")
