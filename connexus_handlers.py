from google.appengine.api import users
from google.appengine.ext import ndb
from Model import Image, Stream, Subscription, ReportSendingRate
import uuid


import webapp2
import jinja2
import os
import urllib
import json
from google.appengine.api import urlfetch
from datetime import datetime
# self defined classes

import webapp2

from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import mail




# SERVICES_URL = 'http://localhost:8080' #local
SERVICE_URL = 'http://ee382v-apt-connexus.appspot.com/'
APP_ID = 'ee382v-apt-connexus'

# Email addresses list
report_email_list = ["ee461lta@gmail.com"]
DEFAULT_SENDING_RATE = 2    # 1 hour
global_last_report_time = None

# HTML_TEMPLATES FOLDER
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class HTTPRequestHandler(webapp2.RequestHandler):
    def callService(self, service, subservice='', **params):
        result = urlfetch.fetch('/'.join([SERVICE_URL, 'svc', service]
                                         + ([subservice] if subservice else []))
                                , payload=json.dumps(params), method=urlfetch.POST
                                , headers={'Accept': 'application/json'})
        jsonresult = json.loads(result.content)

        status = {}
        if 'error' in jsonresult:
            status['error'] = jsonresult['error']
        elif not result.status_code == 200:
            status['error'] = "HTTP %d Error" % result.status_code

        if 'status' in jsonresult:
            status['status'] = jsonresult['status']
        else:
            status['status'] = "HTTP %d" % result.status_code

        if 'error' in status: return self.redirect('/error', status)

        return status, jsonresult

    def render(self, src, **form):
        template = JINJA_ENVIRONMENT.get_template(src)
        self.response.write(template.render(form))

    def redirect(self, url, params=None):
        params = ('?' + urllib.urlencode(params)) if params else ''
        super(HTTPRequestHandler, self).redirect(url + params)


class LoginHandler(HTTPRequestHandler):
    def get(self):
        # Checks for active Google account session
        user = users.get_current_user()
        if user:
            return self.redirect('/manage')
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        template_values = {
            'user': user,
            'url': url,
            'url_linktext': url_linktext,
        }
        template = JINJA_ENVIRONMENT.get_template('WelcomePage.html')
        self.response.write(template.render(template_values))


class ManagePageHandler(HTTPRequestHandler):
    # GET: Render a management html page
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_login_url(self.request.uri)
            logout_linktext = 'Logout'
            streams = ndb.Query(ancestor = ndb.Key('Account', user.user_id())).fetch()

            #get user subscriptions
            subscribed_list = Subscription.query(Subscription.user_id == user.user_id()).fetch()
            subscribed_streams = []
            for subscribed_item in subscribed_list:
                sub_stream = Stream.query(Stream.stream_id == subscribed_item.stream_id).fetch()
                if len(sub_stream) != 0:
                    subscribed_streams.append(sub_stream[0])

            sorted_streams = sorted(streams,key=lambda  stream: stream.last_add, reverse = True )
            template_values = {
                'user': user,
                'url': logout_url,
                'url_linktext': logout_linktext,
                'user_streams': sorted_streams,
                'subscribed_streams':subscribed_streams
            }
            self.render('Management.html', **template_values)
        else:
            self.redirect('/login')


class CreatePageHandler(HTTPRequestHandler):
    # GET: Render a create html page
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_login_url(self.request.uri)
            logout_linktext = 'Logout'
            template_values = {
            'user': user,
            'url': logout_url,
            'url_linktext': logout_linktext,
            }
            self.render('CreateStreamPage.html', **template_values)
        else:
            self.redirect('/login')



class CreateStream(HTTPRequestHandler):
    def post(self):

        user_id = users.get_current_user().user_id()
        stream_name = self.request.get("streamName")
        stream_id = uuid.uuid4()
        cover_url = self.request.get("cover_url")
        content = self.request.get("content")

        new_stream = Stream(parent = ndb.Key('Account', user_id)
                            ,user_id = user_id
                            ,stream_id = str(stream_id)
                            ,stream_name = stream_name
                            # ,last_add = None
                            ,cover_url = cover_url
                            ,views_cnt = 0
                            ,description = content)



        new_stream.put()

        self.redirect('/manage')



class ViewStreamHandler(HTTPRequestHandler):
    def get(self):
        # user_id = self.request.get("user_id")
        curUser = users.get_current_user()
        if curUser:
            stream_id = self.request.get("stream_id")
            stream_lst = Stream.query(Stream.user_id == curUser.user_id(), Stream.stream_id == stream_id).fetch()
            curStream = []
            if len(stream_lst) >= 0:
                curStream = stream_lst[0]
            # create photo upload url
            upload_url = blobstore.create_upload_url('/upload_photo')

            # subscription logic:
            # if the relationship between this stream and the current user exists,
            # then set the <subscribe_option> and <subscribe_url> fields to un-subscribe ones.
            sub_query = Subscription.query(Subscription.user_id == curUser.user_id(), Subscription.stream_id == stream_id).fetch()
            if len(sub_query) != 0:
                # subscription exists
                subscribe_option = "Unsubscribe"
                subscribe_url = "/subscribe?stream_id="+stream_id+"&subscribe_bool=false"
            else:
                # subscription doesn't exist
                subscribe_option = "Subscribe"
                subscribe_url = "/subscribe?stream_id="+stream_id+"&subscribe_bool=true"

            description = "The owner didn't leave any description."
            if curStream.description:
                description = curStream.description
            template_values = {
                'user' : curUser,
                'stream_id' : stream_id,
                'stream_owner': curStream.user_id,
                'blob_key_lst' : curStream.blob_key_lst,
                'image_id_lst' : curStream.image_id_lst,
                'upload_url' : upload_url,
                'length': len(curStream.blob_key_lst),
                'subscribe_option': subscribe_option,
                'subscribe_url' : subscribe_url,
                'stream_name': curStream.stream_name,
                'description': description
            }

            # increase the views_cnt
            curStream.increase_view_cnt()

            template = JINJA_ENVIRONMENT.get_template('ViewStream.html')
            self.response.write(template.render(template_values))
        else:
            self.redirect('/login')





class addImg(blobstore_handlers.BlobstoreUploadHandler):
    def post(self):
        user_id = users.get_current_user().user_id()
        stream_id = self.request.get("stream_id")
        description = self.request.get("description")

        #get the blob store object
        upload = self.get_uploads()[0]
        img_id = uuid.uuid4()
        print "addImg: blob_key: " + str(upload.key())
        user_photo = Image(user_id = users.get_current_user().user_id(),
                           img_id = str(img_id),
                           content = description,
                           blob_key = upload.key()
                            )
        stream_lst = Stream.query(Stream.user_id == user_id, Stream.stream_id == stream_id).fetch()
        curStream = stream_lst[0]
        if curStream:
            print "addImg>> stream id:", stream_id, ", list length: ", len(stream_lst)
            curStream.addImage(user_photo)
        else:
            print "Fail to add user photo ", user_photo, "to stream ", stream_id

        self.redirect('/viewStream?'+'stream_id='+stream_id)


class deleteImg(HTTPRequestHandler):
    def get(self):
        photo_Key = self.request.get("photo_Key")
        stream_id = self.request.get("stream_id")
        user_id = users.get_current_user().user_id()
        stream_lst = Stream.query(Stream.user_id == user_id, Stream.stream_id == stream_id).fetch()
        img_lst = Image.query(Image.user_id == user_id, Image.img_id == photo_Key).fetch()
        curStream = stream_lst[0]
        curImg = img_lst[0]
        curStream.deleteImage(curImg)
        self.redirect('/viewStream?'+'stream_id='+stream_id)



class ViewPhotoHandler(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, photo_key):
        print "key in handle: " + photo_key
        if not blobstore.get(photo_key):
            print "no photo-key"
            self.error(404)
        else:
            print "photo_key: " + str(photo_key)
            self.send_blob(photo_key)

class deleteStream(HTTPRequestHandler):
    def get(self):
        stream_id = self.request.get("stream_id")
        user_id = users.get_current_user().user_id()
        stream_lst = Stream.query(Stream.user_id == user_id, Stream.stream_id == stream_id).fetch()
        curStream = stream_lst[0]
        curStream.deleteStream()
        self.redirect('/manage')

class deleteStreamAll(HTTPRequestHandler):
    def get(self):
        user_id = users.get_current_user().user_id()
        stream_lst = Stream.query(Stream.user_id == user_id).fetch()
        print stream_lst
        for stream in stream_lst:
            print stream
            stream.deleteStream()
        self.redirect('/manage')


class viewAllStream(HTTPRequestHandler):
    def get(self):
        user_id = users.get_current_user().user_id()

        stream_lst = Stream.query().fetch()

        logout_url = users.create_login_url(self.request.uri)
        logout_linktext = 'Logout'

        sorted_streams = sorted(stream_lst,key=lambda  stream: stream.last_add, reverse = True )

        template_values = {
            'streams' : sorted_streams,
            'length': len(sorted_streams),
            'user' : users.get_current_user(),
            'url': logout_url,
            'url_linktext': logout_linktext,
        }
        self.render('ViewAllStream.html', **template_values)

# Subscription handler class:
#   process get requests for both subscribing and un-subscribing
#   required fields: stream_id; (user exists in the request).
class SubscriptionHandler(HTTPRequestHandler):
    def get(self):
        stream_id = self.request.get('stream_id')
        current_user = users.get_current_user()
        if current_user and stream_id:
            # check if the request is to subscribe or un-subscribe
            subscribe_bool = self.request.get('subscribe_bool') == 'true'
            if subscribe_bool:
                # subscribing request
                new_subscription_entry = Subscription(user_id = current_user.user_id(),
                                           stream_id = stream_id)
                new_subscription_entry.put()
                print 'SubscriptionHandler:: user' + current_user.user_id() + ' subscribed to stream' + stream_id
                self.redirect('/manage')
            else:
                # ub-subscribing request
                # fetch the data entry of this subscription
                subscription_entry = Subscription.query(Subscription.stream_id == stream_id, Subscription.user_id == current_user.user_id()).fetch()
                if len(subscription_entry) != 0:
                    subscription_entry[0].deleteSubscription()
                    print 'SubscriptionHandler:: user' + current_user.user_id() + ' un-subscribed to stream' + stream_id
                    self.redirect('/manage')
                else:
                    # no such subscription entry can be found
                    template_values = {
                        'error_msg' : "no such subscription entry can be found. (userid=" + current_user.user_id() +", streamid="+ stream_id + ")"
                    }
                    self.render("Error.html", **template_values)
        else:
            #no user can be found in the session; transfer to error page
            template_values = {
                'error_msg' : "no user can be found in the session"
            }
            self.render("Error.html", **template_values)


# Trending Page handler:
#
class TrendingPageHandler(HTTPRequestHandler):
    def get(self):
        trending_stream_lst = Stream.query().order(-Stream.views_cnt).fetch(3)

        template_values = {
            'trending_stream_lst': trending_stream_lst
        }
        self.render('Trending.html', **template_values)



class SearchHandler(HTTPRequestHandler):
    def get(self):
        user_id = users.get_current_user().user_id()
        logout_url = users.create_login_url(self.request.uri)
        logout_linktext = 'Logout'
        template_values = {
            'user' : users.get_current_user(),
            'url': logout_url,
            'url_linktext': logout_linktext,
        }
        self.render('Search.html', **template_values)


class SearchRequestHandler(HTTPRequestHandler):
    def post(self):
        type = self.request.get("type")
        user_id = users.get_current_user().user_id()
        keyWord = self.request.get("keyWord")
        searchItem = keyWord.lower()
        stream_lst = Stream.query().fetch()
        return_lst = []

        if type == "title":
            for stream in stream_lst:
                if stream.stream_name != None:
                    if searchItem in stream.stream_name.lower():
                        return_lst.append(stream)
        else:
            for stream in stream_lst:
                if  stream.description != None:
                    if searchItem in stream.description.lower():
                        return_lst.append(stream)


        logout_url = users.create_login_url(self.request.uri)
        logout_linktext = 'Logout'

        sorted_streams = sorted(return_lst,key=lambda  stream: stream.last_add, reverse = True )


        template_values = {
            'streams' :  sorted_streams,
            'length': len(  sorted_streams),
            'user' : users.get_current_user(),
            'url': logout_url,
            'url_linktext': logout_linktext,
        }
        self.render('ViewAllStream.html', **template_values)

# cron job getting called every hour
# rewind the view counts
class ResetTrendingViewCnts(HTTPRequestHandler):
    def get(self):
        all_streams_lst = Stream.all()
        print 'Cron job executing ... cleaning the view counts for ', len(all_streams_lst), ' streams.'
        for stream in all_streams_lst:
            stream.reset_view_cnt()

# This handler catches the event of updating the sending rate
class UpdateReportSendingRate(HTTPRequestHandler):
    def get(self):
        upd_send_rate = self.request.get("sending_rate")
        print '[UpdateReportSendingRate]:: get sending_rate update: ', upd_send_rate

        reportRate = ReportSendingRate.query().fetch()
        if len(reportRate) != 0:
            ori_send_rate = reportRate[0].sending_rate
            reportRate[0].update_sending_rate(int(upd_send_rate))
            print '[UpdateReportSendingRate]:: change sending rate from ', ori_send_rate, ' to ', upd_send_rate
        else:
            print "[UpdateReportSendingRate]:: cannot find the sending rate configuration. Setting the sending rate " \
                  "to 1 hour"
            dft_send_rate = ReportSendingRate(user_email = report_email_list[0],
                                              sending_rate = DEFAULT_SENDING_RATE)
            dft_send_rate.put()

        self.redirect('/trending')

# This is the actual cron job which sends the email report to the user.
class SendReportCronJob(HTTPRequestHandler):
    def get(self):
        # get the last report time
        global global_last_report_time
        if not global_last_report_time:
            global_last_report_time = datetime.now()
            return

        # get the sending rate
        reportRate = ReportSendingRate.query().fetch()
        if len(reportRate) != 0:
             reportRate = reportRate[0].sending_rate
        interval_in_mins = -99
        if reportRate == 0:
            # No reports. Return
            return
        elif reportRate == 1:
            interval_in_mins = 5
        elif reportRate == 2:
            interval_in_mins = 60
        elif reportRate == 3:
            interval_in_mins = 1440     # one day
        else:
            print 'Error in report rate : ', reportRate

        # comparing the sending rate with the time interval since the last report
        time_passed = (datetime.now() - global_last_report_time).seconds
        if time_passed < int(interval_in_mins)*60:
            return

        # send the report mail
        global_last_report_time = datetime.now()
        trending_stream_lst = Stream.query().order(-Stream.views_cnt).fetch(3)

        sender_mail_addr = "trendingStreams@"+APP_ID+".appspotmail.com"
        subject = "Trending Streams from Connexus " + global_last_report_time
        body = """ Here are the trending streams on Connexus now: \n
        1) %s - %s  \n
        2) %s - %s  \n
        3) %s - %s  \n
        """ % (trending_stream_lst[0].stream_name,
               trending_stream_lst[0].user_id,
               trending_stream_lst[1].stream_name,
               trending_stream_lst[1].user_id,
               trending_stream_lst[2].stream_name,
               trending_stream_lst[2].user_id)

        for receiver_addr in report_email_list:
            mail.send_mail(sender_mail_addr, receiver_addr, subject, body)

        print "Successfully sent the trending email to " + report_email_list

app = webapp2.WSGIApplication([
    ('/', LoginHandler)
    , ('/login', LoginHandler)
    , ('/manage', ManagePageHandler)
    , ('/create', CreatePageHandler)
    , ('/createStream', CreateStream)
    , ('/deleteStream', deleteStream)
    , ('/viewStream', ViewStreamHandler)
    , ('/viewAllStream', viewAllStream)
    , ('/view_photo/([^/]+)?', ViewPhotoHandler)
    , ('/upload_photo', addImg)
    , ('/stream/delete', deleteImg)
    , ('/deleteStream/all', deleteStreamAll)
    , ('/subscribe', SubscriptionHandler)
    , ('/trending', TrendingPageHandler)
    , ('/search', SearchHandler)
    , ('/search/result', SearchRequestHandler)
    , ('/cron/resetViewsCnt', ResetTrendingViewCnts)
    , ('/updateReportSendingRate', UpdateReportSendingRate)]
    , debug=True)
