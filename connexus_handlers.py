from google.appengine.api import users
from google.appengine.ext import ndb

import webapp2
import jinja2
import os
import urllib
import json
from google.appengine.api import urlfetch
# self defined classes
from Stream_services import StreamService


# SERVICES_URL = 'http://localhost:8080' #local
SERVICE_URL = 'http://ee382v-apt-miniproject.appspot.com/'

# HTML_TEMPLATES FOLDER
JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader('HtmlTemplates'),
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
            template_values = {
            'user': user,
            'url': logout_url,
            'url_linktext': logout_linktext,
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



app = webapp2.WSGIApplication([
    ('/', LoginHandler)
    , ('/login', LoginHandler)
    , ('/manage', ManagePageHandler)
    , ('/create', CreatePageHandler)
    , ('/StreamServices', StreamService)]
    , debug=True)
