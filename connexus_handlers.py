from Model import Image, Stream, Subscription, ReportSendingRate

import webapp2

import urllib
import json
from google.appengine.api import urlfetch
from datetime import datetime
# self defined classes

from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.api import mail


#   import the services
from web_services import *

#   import the constants
from Constants import *


# Email addresses list
report_email_list = ["ee461lta@gmail.com"]
DEFAULT_SENDING_RATE = 2    # 1 hour
global_last_report_time = None


class HTTPRequestHandler(webapp2.RequestHandler):
    def callService(self, service, subservice='', **params):
        result = urlfetch.fetch('/'.join([SERVICE_URL, 'ws', service]
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
            logout_url = users.create_logout_url(self.request.uri)
            logout_linktext = 'Logout'

            # call service to get all streams
            status, result = self.callService('stream', 'query', user_email=user.email(),
                                                         check_subscription=False)

            user_streams_list = result[IDENTIFIER_USER_STREAM_LIST]

            # get user subscriptions
            status, result = self.callService('stream', 'query', user_email=user.email(),
                                                         check_subscription=True)
            user_sub_streams_list = result[IDENTIFIER_USER_SUB_STREAM_LIST]

            template_values = {
                'user': user,
                'url': logout_url,
                'url_linktext': logout_linktext,
                'user_streams': user_streams_list,
                'subscribed_streams': user_sub_streams_list
            }
            self.render('Management.html', **template_values)
        else:

            self.redirect('/login')


class CreatePageHandler(HTTPRequestHandler):
    # GET: Render a create html page
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url(self.request.uri)
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

        user_email = users.get_current_user().email()
        stream_name = self.request.get(IDENTIFIER_STREAM_NAME)
        cover_url = self.request.get(IDENTIFIER_COVER_URL)
        stream_description = self.request.get(IDENTIFIER_STREAM_DESC)

        self.callService('stream', 'create', user_email=user_email, stream_name=stream_name, cover_url=cover_url,
                         stream_description=stream_description)

        self.redirect('/manage')


class ViewStreamHandler(HTTPRequestHandler):
    def get(self):
        cur_user = users.get_current_user()
        if cur_user:
            url = users.create_logout_url(self.request.uri)
            stream_id = self.request.get(IDENTIFIER_STREAM_ID)
            img_req_page = self.request.get(IDENTIFIER_IMG_REQ_PAGE)
            if not img_req_page:
                img_req_page = '0'    # default img idx lst

            status, result = self.callService('stream', 'view', stream_id=stream_id,
                                              img_req_page=img_req_page)

            # Subscription logic
            status, sub_result = self.callService('stream', 'subscribe', stream_id=stream_id,
                                                  user_email=cur_user.email())

            # create photo upload url
            # it should redirect to the ViewStream page
            if cur_user.email() == result[IDENTIFIER_STREAM_OWNER]:
                # redirect = '/viewStream/?' + urllib.urlencode({ IDENTIFIER_STREAM_ID: stream_id })
                upload_url = blobstore.create_upload_url('/ws/stream/upload_image')
                print 'ViewStreamHandler >> generate upload url: ', upload_url
                # redirect_url = '/ws/stream/upload_image?' + urllib.urlencode({IDENTIFIER_STREAM_ID: stream_id})

            template_values = {
                IDENTIFIER_CURRENT_USER: cur_user,
                IDENTIFIER_URL: url,
                IDENTIFIER_STREAM_OWNER: result[IDENTIFIER_STREAM_OWNER],
                IDENTIFIER_STREAM_NAME: result[IDENTIFIER_STREAM_NAME],
                IDENTIFIER_STREAM_ID: stream_id,
                IDENTIFIER_STREAM_DESC: result[IDENTIFIER_STREAM_DESC],
                IDENTIFIER_IMG_IDX_RES_LIST: result[IDENTIFIER_IMG_IDX_RES_LIST],
                IDENTIFIER_IMAGEID_LIST: result[IDENTIFIER_IMAGEID_LIST],
                IDENTIFIER_BLOBKEY_LIST: result[IDENTIFIER_BLOBKEY_LIST],
                IDENTIFIER_SUBSCRIPTION_OPTION: sub_result[IDENTIFIER_SUBSCRIPTION_OPTION],
                IDENTIFIER_SUBSCRIPTION_URL: sub_result[IDENTIFIER_SUBSCRIPTION_URL],
                # prev/next page indexes
                IDENTIFIER_NEXT_PG_IDX: result[IDENTIFIER_NEXT_PG_IDX],
                IDENTIFIER_PREV_PG_IDX: result[IDENTIFIER_PREV_PG_IDX],

                IDENTIFIER_UPLOAD_URL: upload_url
            }

            # Geo View
            is_geo_view = self.request.get(IDENTIFIER_GEO_VIEW)
            if not is_geo_view:
                self.render("ViewStream.html", **template_values)
            else:
                self.render("ViewStream_Geo.html", **template_values)

        else:
            self.redirect('/login')


# Subscription handler class:
#   process get requests for both subscribing and un-subscribing
#   required fields: stream_id; (user exists in the request).
class SubscriptionHandler(HTTPRequestHandler):
    def get(self):
        stream_id = self.request.get(IDENTIFIER_STREAM_ID)
        user_email = self.request.get(IDENTIFIER_USER_EMAIL)
        if user_email and stream_id:
            # check if the request is to subscribe or un-subscribe
            subscribe_bool = self.request.get('subscribe_bool') == 'true'
            if subscribe_bool:
                # subscribing request
                new_subscription_entry = Subscription(user_email=user_email, stream_id=stream_id)
                new_subscription_entry.put()
                print 'SubscriptionHandler:: user' + user_email + ' subscribed to stream' + stream_id
                self.redirect('/manage')
            else:
                # ub-subscribing request
                # fetch the data entry of this subscription
                subscription_entry = Subscription.query(Subscription.stream_id == stream_id,
                                                        Subscription.user_email == user_email).fetch()
                if len(subscription_entry) != 0:
                    subscription_entry[0].deleteSubscription()
                    print 'SubscriptionHandler:: user' + user_email + ' un-subscribed to stream' + stream_id
                    self.redirect('/manage')
                else:
                    # no such subscription entry can be found
                    template_values = {
                        'error_msg' : "no such subscription entry can be found. (userid=" + user_email
                                      + ", streamid=" + stream_id + ")"
                    }
                    self.render("Error.html", **template_values)
        else:
            #no user can be found in the session; transfer to error page
            template_values = {
                'error_msg' : "no user can be found in the session"
            }
            self.render("Error.html", **template_values)


class RemoveImageHandler(HTTPRequestHandler):
    def get(self):
        user_email = users.get_current_user().email()
        photo_Key = self.request.get("photo_Key")
        stream_id = self.request.get("stream_id")

        # call service
        status, result = self.callService('stream', 'remove_image', user_email=user_email, stream_id=stream_id,
                                          photo_key=photo_Key)

        self.redirect('/viewStream?'+'stream_id='+stream_id)


# class ViewPhotoHandler(blobstore_handlers.BlobstoreDownloadHandler):
#     def get(self, photo_key):
#         # print "key in handle: " + photo_key
#         if not blobstore.get(photo_key):
#             print "no photo-key"
#             self.error(404)
#         else:
#             print "photo_key: " + str(photo_key)
#             self.send_blob(photo_key)


class deleteStream(HTTPRequestHandler):
    def get(self):
        stream_id = self.request.get("stream_id")
        user_email = users.get_current_user().email()
        stream_lst = Stream.query(Stream.user_email == user_email, Stream.stream_id == stream_id).fetch()
        curStream = stream_lst[0]
        curStream.deleteStream()
        self.redirect('/manage')


class deleteStreamAll(HTTPRequestHandler):
    def get(self):
        user_email = users.get_current_user().email()
        stream_lst = Stream.query(Stream.user_email == user_email).fetch()
        print stream_lst
        for stream in stream_lst:
            print stream
            stream.deleteStream()
        self.redirect('/manage')


class viewAllStream(HTTPRequestHandler):
    def get(self):
        user_email = users.get_current_user().email()

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
        user_email = users.get_current_user().email()
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
        user_email = users.get_current_user().email()
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
        all_streams_lst = Stream.query().fetch()
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

        print '[Cron::SendReportCronJob] started'

        # get the last report time
        global global_last_report_time
        if not global_last_report_time:
            global_last_report_time = datetime.now()
            return

        print '[Cron::SendReportCronJob] global_last_report_time:', global_last_report_time
        # get the sending rate
        reportRate = ReportSendingRate.query().fetch()

        if len(reportRate) != 0:
             reportRate = reportRate[0].sending_rate

        print '[Cron::SendReportCronJob] reportRate:', reportRate
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
        print '[Cron::SendReportCronJob] time_passed:', time_passed
        if time_passed < int(interval_in_mins)*60:
            return

        # send the report mail
        trending_stream_lst = Stream.query().order(-Stream.views_cnt).fetch(3)

        sender_mail_addr = REPORT_SENDER_NAME + "@" + APP_ID + MAILBOX_SURFIX
        subject = "Trending Streams from Connexus " + str(global_last_report_time)
        body = """ Here are the trending streams on Connexus now: \n
        1) %s - %s  \n
        2) %s - %s  \n
        3) %s - %s  \n
        """ % (trending_stream_lst[0].stream_name,
               trending_stream_lst[0].user_email,
               trending_stream_lst[1].stream_name,
               trending_stream_lst[1].user_email,
               trending_stream_lst[2].stream_name,
               trending_stream_lst[2].user_email)

        for receiver_addr in report_email_list:
            mail.send_mail(sender_mail_addr, receiver_addr, subject, body)

        print "Successfully sent the trending email to " + str(report_email_list)
        #reset the timer
        global_last_report_time = datetime.now()


# Error message page
class ErrorHandler(HTTPRequestHandler):
    def get(self):
        template_values={}
        template_values['error_msg'] = self.request.get('error_msg')
        self.render("Error.html", **template_values)


# # Error message page
# class UploadUrlRequestHandler(HTTPRequestHandler):
#     def get(self):
#         upload_url = blobstore.create_upload_url('/ws/stream/upload_image')
#         print 'UploadUrlRequestHandler >> generate a new upload url: ', upload_url
#         self.response.write(upload_url)


# Auto Complete Handler
# Service Address: /autocomplete
class AutoCompleteHandler(HTTPRequestHandler):
    def get(self):
        pattern = self.request.get("term")
        stream_lst = Stream.query().fetch()
        ret_lst = []
        if pattern:
            for stream in stream_lst:
                if pattern in stream.stream_name:
                    ret_lst.append(stream.stream_name)
        ret_lst.sort()
        if len(ret_lst) == 0:
            valid = False
        else:
            valid = True
        context = {"valid": valid, "ret_lst": ret_lst}
        self.response.write(json.dumps(context))


app = webapp2.WSGIApplication([
    ('/', LoginHandler),
    ('/login', LoginHandler),
    ('/manage', ManagePageHandler),
    ('/create', CreatePageHandler),
    ('/createStream', CreateStream),
    ('/deleteStream', deleteStream),
    ('/viewStream', ViewStreamHandler),
    ('/viewAllStream', viewAllStream),
    # ('/view_photo/([^/]+)?', ViewPhotoHandler),
    # , ('/upload_photo', addImg)
    ('/stream/delete', RemoveImageHandler),
    ('/deleteStream/all', deleteStreamAll),
    ('/trending', TrendingPageHandler),
    ('/search', SearchHandler),
    ('/search/result', SearchRequestHandler),
    ('/cron/reset_views_cnt', ResetTrendingViewCnts),
    ('/updateReportSendingRate', UpdateReportSendingRate),
    ('/cron/send_report', SendReportCronJob),
    ('/error', ErrorHandler),
    # ('/upload_url_generate', UploadUrlRequestHandler),
    ('/autoComplete', AutoCompleteHandler),
    #below are the web services
    ('/ws/stream/view', ViewStreamService),
    ('/ws/stream/subscribe', SubscriptionService),
    ('/subscribe', SubscriptionHandler),
    ('/ws/stream/upload_image', UploadImageService),
    ('/ws/stream/create', CreateStreamService),
    ('/ws/stream/query', StreamQueryService),
    ('/ws/stream/remove_image', RemoveImageService),
    ('/ws/stream/marker_query', MarkersQueryService),
    ('/view_photo/([^/]+)?', ViewImageService),
    ('/ws/stream/view_all', mViewAllStreamsService),
    ('/ws/stream/m_view_single_stream', mViewSingleStreamService),
    ('/ws/stream/m_view_nearby_photos', mViewNearbyImages),
    ('/ws/stream/m_search', mSearchStreams),
    ('/ws/stream/m_get_upload_url', mGetUploadURL)
    ]


    , debug=True)
