from google.appengine.api import users
from google.appengine.ext import ndb
from Model import Image, Stream
import uuid


import webapp2
import jinja2
import os
import urllib
import json
from google.appengine.api import urlfetch
# self defined classes

import webapp2

from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.webapp.util import run_wsgi_app




# SERVICES_URL = 'http://localhost:8080' #local
SERVICE_URL = 'http://ee382v-apt-miniproject.appspot.com/'

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

            template_values = {
                'user': user,
                'url': logout_url,
                'url_linktext': logout_linktext,
                'user_streams': streams
            }
            self.render('management.html', **template_values)
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

        new_stream = Stream(parent = ndb.Key('Account', user_id)
                            ,user_id = user_id
                            ,stream_id = str(stream_id)
                            ,stream_name = stream_name
                            ,last_add = None
                            ,cover_url = cover_url)



        new_stream.put()

        self.redirect('/manage')

class viewStream(HTTPRequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            stream_id = self.request.get("stream_id")
            stream_lst = Stream.query(Stream.user_id == user.user_id(), Stream.stream_id == stream_id).fetch()
            curStream = stream_lst[0]
            # create photo upload url
            upload_url = blobstore.create_upload_url('/upload_photo')
            template_values = {
                'user' : user,
                'stream_id' : stream_id,
                'blob_key_lst' : curStream.blob_key_lst,
                'image_id_lst' : curStream.image_id_lst,
                'upload_url' : upload_url
            }

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

        # url = self.request.get()

        self.redirect('/viewstream?'+'stream_id='+stream_id)


class deleteImg(HTTPRequestHandler):
    def get(self):
        pass


class ViewPhotoHandler(blobstore_handlers.BlobstoreDownloadHandler):
    def get(self, photo_key):
        if not blobstore.get(photo_key):
            self.error(404)
        else:
            self.send_blob(photo_key)



app = webapp2.WSGIApplication([
    ('/', LoginHandler)
    , ('/login', LoginHandler)
    , ('/manage', ManagePageHandler)
    , ('/create', CreatePageHandler)
    , ('/createStream', CreateStream)
    , ('/viewstream', viewStream)
    , ('/view_photo/([^/]+)?', ViewPhotoHandler)
    , ('/upload_photo', addImg)
    , ('stream/delete', deleteImg)]
    , debug=True)
