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

from math import sin, cos, sqrt, atan2, radians

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

        self.respond(stream_owner=stream.user_email, image_res_idx_lst=image_res_idx_lst, blob_key_lst=blob_key_lst,
                     image_id_lst=image_id_lst, stream_name=stream.stream_name, stream_description=stream.description,
                     next_page_idx=next_pg_idx, prev_page_idx=prev_pg_idx,
                     status="Retrieved image indexes %r from stream %r" % (image_id_lst, stream_id))


#   /ws/stream/create
class CreateStreamService(ServiceHandler):
    def post(self):
        req_json = json.loads(self.request.body)
        user_email = req_json[IDENTIFIER_USER_EMAIL]
        stream_name = req_json[IDENTIFIER_STREAM_NAME]
        stream_id = uuid.uuid4()
        cover_url = req_json[IDENTIFIER_COVER_URL]
        description = req_json[IDENTIFIER_STREAM_DESC]

        new_stream = Stream(parent=ndb.Key('Account', user_email),
                            user_email=user_email,
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
        current_user_email = req_json[IDENTIFIER_USER_EMAIL]
        print "SubscriptionService >> checking subscription stream_id: " + stream_id + ", user_email:" + current_user_email
        sub_query = Subscription.query(Subscription.user_email == current_user_email, Subscription.stream_id == stream_id).fetch()
        if len(sub_query) != 0:
            # subscription exists
            subscribe_option = "Unsubscribe"
            subscribe_url = "/subscribe?stream_id="+stream_id+"&subscribe_bool=false"\
                            + "&"+IDENTIFIER_USER_EMAIL+"=" + current_user_email
        else:
            # subscription doesn't exist
            subscribe_option = "Subscribe"
            subscribe_url = "/subscribe?stream_id="+stream_id+"&subscribe_bool=true"\
                            + "&"+IDENTIFIER_USER_EMAIL+"=" + current_user_email
        self.respond(subscribe_option=subscribe_option, subscribe_url=subscribe_url, status="success")


# Blobstore related services
# ViewImageService
class ViewImageService(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, photo_key):
        # blob_key = self.request.get(KEYWORD_BLOBKEY)
        if not blobstore.get(photo_key):
            self.error(404)
        else:
            self.send_blob(photo_key)


# RemoveImageService
# Service Address: /ws/stream/remove_image
# Request Fields: IDENTIFIER_USER_EMAIL, IDENTIFIER_STREAM_ID, IDENTIFIER_IMAGEID
class RemoveImageService(ServiceHandler):
    def post(self):
        req_json = json.loads(self.request.body)
        stream_id = req_json[IDENTIFIER_STREAM_ID]
        current_user_email = req_json[IDENTIFIER_USER_EMAIL]
        photo_key = req_json[IDENTIFIER_PHOTO_KEY]

        response = {}
        stream = Stream.get_stream(stream_id)

        if not (stream_id and current_user_email and photo_key and stream):
            response['error'] = "Failed to find photo_key (" + photo_key + ") for user (" + current_user_email \
                                + ") under stream(" + stream_id+")."
            self.respond(**response)
        elif stream.user_id != current_user_email:
            response['error'] = "Failed to remove image user (" + current_user_email \
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
        user_email = self.request.get(IDENTIFIER_USER_EMAIL)
        stream_id = self.request.get(IDENTIFIER_STREAM_ID)
        description = self.request.get(IDENTIFIER_STREAM_DESC)
        location = self.request.get(IDENTIFIER_LOCATION)

        print 'UploadImageService >> get upload image request ', len(self.get_uploads())

        for upload in self.get_uploads():
            #get the blob store object
            # upload = self.get_uploads()[0]
            image_id = uuid.uuid4()
            print "UploadImageService >> Upload new image with blob_key: " + str(upload.key())

            if not location:
                # Generate a random location - Phase II requirement
                location = ndb.GeoPt(random.uniform(-90, 90), random.uniform(0, 90))
            else:
                loc_cor = location.split("_")
                if len(loc_cor)!=2:
                    print "length of the location parameter is not 2. (", location, ")"
                location = ndb.GeoPt(long(float(loc_cor[0])), long(float(loc_cor[1])))

            user_image = Image(user_email=user_email,
                               img_id=str(image_id),
                               content=description,
                               blob_key=upload.key(),
                               location=location)
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
# Request Fields: IDENTIFIER_USER_EMAIL(str), IDENTIFIER_CHECK_SUBSCRIPTION(boolean)
class StreamQueryService(ServiceHandler):
    def post(self):
        req_json = json.loads(self.request.body)
        user_email = req_json[IDENTIFIER_USER_EMAIL]
        is_check_subscription = req_json[IDENTIFIER_CHECK_SUBSCRIPTION]
        if not is_check_subscription:
            print 'StreamQueryService >> checking all streams created by user[', user_email, ']'
            user_streams_list = ndb.Query(ancestor=ndb.Key('Account', user_email)).fetch()
            sorted_streams_list = sorted(user_streams_list, key=lambda stream: stream.last_add, reverse=True)
            sid_list = []
            for stream in sorted_streams_list:
                sid_list.append(stream.stream_id)

            dumpablelist = [Stream.get_stream(stream_id).dumpStream()
                            for stream_id in sid_list]

            self.respond(user_streams_list=dumpablelist, status="success")

        else:
            print 'StreamQueryService >> checking all streams subscribed by user[', user_email, ']'
            subscribed_list = Subscription.query(Subscription.user_email == user_email).fetch()
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

        stream_id = self.request.get(IDENTIFIER_STREAM_ID)

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
                    markers_lst.append(marker)
            self.respond(markers=markers_lst, status="success")


# Service for getting a list of all streams
# Service Address: /ws/stream/view_all
# Return: stream_id_lst, stream_name_lst , cover_img_url_list, startIdx
# Request Fields: None
class mViewAllStreamsService(ServiceHandler):
    def get(self):
        stream_id_lst=list()
        stream_name_lst=list()
        cover_img_url_list=list()
        stream_lst=list()

        is_view_all_subscribed = self.request.get(IS_VIEW_ALL_SUBSCRIBED)
        usr_id = self.request.get(IDENTIFIER_USER_EMAIL)

        if is_view_all_subscribed:
            print 'mViewAllStreamsService:: getting subscribed streams list for user', usr_id

            subscribed_list = Subscription.query(Subscription.user_email == usr_id).fetch()
            for subscribed_item in subscribed_list:
                stream_lst.append(Stream.get_stream(subscribed_item.stream_id))

        else:
            print 'mViewAllStreamsService:: getting all streams list'
            stream_lst = Stream.query().fetch()

        sorted_streams = sorted(stream_lst, key=lambda stream:stream.last_add, reverse=True)

        nrof_streams = len(sorted_streams)

        start_idx = self.request.get(VIEW_ALL_START_INDEX)
        if not start_idx or (start_idx > nrof_streams):
            start_idx = 0

        last_idx = start_idx+NUM_STREAMS_PER_PAGE
        if last_idx > nrof_streams:
            last_idx = nrof_streams-1

        for i in xrange(start_idx, last_idx+1):
            stream = sorted_streams[i]
            stream_id_lst.append(stream.stream_id)
            stream_name_lst.append(stream.stream_name)
            cover_img_url_list.append(stream.cover_url)

        print "mViewAllStreamsService:: stream_id_lst:" + str(stream_id_lst) + " |||| stream_name_lst:" + \
              str(stream_name_lst) + " |||| cover_img_url_list:" + str(cover_img_url_list) + " |||| last_idx:" + \
              str(last_idx)

        self.respond(stream_id_lst=stream_id_lst, stream_name_lst=stream_name_lst,
                     cover_img_url_list=cover_img_url_list, last_idx=last_idx, status="success")


# Service for getting a list of images from a stream
# Service Address: /ws/stream/m_view_single_stream
# Return: stream_owner, stream_name, img_id_lst, img_url_lst, upload_url, last_idx, nrof_imgs_in_stream
# Request Fields: stream_id, start_idx
class mViewSingleStreamService(ServiceHandler):
    def get(self):
        stream_id = self.request.get(IDENTIFIER_STREAM_ID)
        start_idx = self.request.get(VIEW_STREAM_START_INDEX)

        if not start_idx:
            start_idx = 0
        else:
            start_idx = int(start_idx)

        stream_obj = Stream()
        stream = stream_obj.get_stream(stream_id)

        # check if the stream exists
        if not stream:
            return self.respond(error="ViewStreamService >> Requested stream id %s does not exist." % stream_id)

        # now start retrieving images
        img_id_lst = []  # saving img ids
        img_url_lst = []
        stream_img_id_lst = stream.image_id_lst

        nrof_imgs_in_stream = len(stream_img_id_lst)

        last_idx = start_idx + NUM_STREAMS_PER_PAGE

        if last_idx >= nrof_imgs_in_stream:
            last_idx = nrof_imgs_in_stream-1

        idx_lst = xrange(start_idx, last_idx)

        for img_idx in idx_lst:
            img_id = stream_img_id_lst[img_idx]
            img_id_lst.append(img_id)
            image = Image.get_image(img_id)
            img_url_lst.append(SERVICE_URL+"/view_photo/"+str(image.blob_key))

        # increase view count
        stream.increase_view_cnt()

        # generate upload url
        upload_url = blobstore.create_upload_url('/ws/stream/view_imgs')

        self.respond(stream_owner=stream.user_email, stream_name=stream.stream_name, img_id_lst=img_id_lst,
                     img_url_lst=img_url_lst, last_idx=last_idx, nrof_imgs_in_stream=nrof_imgs_in_stream,
                     upload_url=upload_url, status="success")


# Service for getting a list of images sorted by location
# Service Address: ws/stream/m_view_nearby_photos
# Return: img_url_lst, distance_lst, stream_id_lst
# Request Fields: location.getLatitude() + "_" + location.getLongitude()
class mViewNearbyImages(ServiceHandler):
    def get(self):
        stream_obj = Stream()
        print "mViewNearbyImages:: starts~"

        loc_str = self.request.get("loc_str")
        loc = loc_str.split('_')
        lat = float(loc[0])
        lon = float(loc[1])

        print "mViewNearbyImages:: get location", lat, lon
        images = Image.query().fetch()

        sorted_imgs = sorted(images, key=lambda image: image.date, reverse=True)

        max_idx = len(sorted_imgs)

        print "mViewNearbyImages:: len(sorted_imgs)=", max_idx

        if max_idx >= NUM_IMG_PER_PAGE:
            max_idx = NUM_IMG_PER_PAGE

        img_url_lst = list()
        stream_id_lst = list()
        distance_lst = list()

        R = 6373.0
        r_m_lat = radians(lat)
        r_m_lon = radians(lon)

        for idx in xrange(0, max_idx):
            image = sorted_imgs[idx]
            img_url_lst.append(SERVICE_URL+"/view_photo/"+str(image.blob_key))
            stream_id_lst.append(stream_obj.get_stream_id_by_img_id(image.img_id))

            img_lat = radians(image.location.lat)
            img_lon = radians(image.location.lon)
            dlat = r_m_lat - img_lat
            dlon = r_m_lon - img_lon
            a = (sin(dlat / 2)) ** 2 + cos(r_m_lat) * cos(img_lat) * (sin(dlon / 2)) ** 2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            distance = R * c

            distance_lst.append(distance)

        print "mViewNearbyImages:: ldistance_lst=", str(distance_lst)

        self.respond(img_url_lst=img_url_lst, stream_id_lst=stream_id_lst, distance_lst=distance_lst, status="success")


# Service for getting a list of stream by name or description
# Service Address: ws/stream/m_search
# Return: stream_id_lst, stream_name_lst, cover_img_url_list
# Request Fields: search_keyword, search_type
class mSearchStreams(ServiceHandler):
    def get(self):
        # get parameters from the request
        search_keyword = self.request.get(IDENTIFIER_SEARCH_KEYWORD)
        search_type = self.request.get(IDENTIFIER_SEARCH_TYPE)
        search_keyword = str(search_keyword).lower()

        # query streams
        stream_lst = Stream.query().fetch()
        res_stream_lst = []
        stream_id_lst = []
        stream_name_lst = []
        cover_img_url_list = []

        if search_type == "title":
            for stream_iter in stream_lst:
                if stream_iter.stream_name:
                    if search_keyword in stream_iter.stream_name.lower():
                        res_stream_lst.append(stream_iter)
        else:
            for stream_iter in stream_lst:
                if stream_iter.description:
                    if search_keyword in stream_iter.description.lower():
                        res_stream_lst.append(stream_iter)

        res_stream_lst = sorted(res_stream_lst, key=lambda stream:stream.last_add, reverse=True)

        for stream_itr in res_stream_lst:
            stream_id_lst.append(stream_itr.stream_id)
            stream_name_lst.append(stream_itr.stream_name)
            cover_img_url_list.append(stream_itr.cover_url)

        self.respond(stream_id_lst=stream_id_lst, stream_name_lst=stream_name_lst,
                     cover_img_url_list=cover_img_url_list, status="success")


# Service for getting a list of stream by name or description
# Service Address: /ws/stream/m_get_upload_url
# Return: upload_url
# Request Fields: None.
class mGetUploadURL(ServiceHandler):
    def get(self):
        upload_url = blobstore.create_upload_url('/ws/stream/upload_image')
        self.respond(upload_url=upload_url, status="success")