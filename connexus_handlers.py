from google.appengine.api import users

import webapp2


class LoginPage(webapp2.RedirectHandler):
    def get(self, *args, **kwargs):
         # Checks for active Google account session
        user = users.get_current_user()

        if user:
            self.response.headers['Content-Type'] = 'text/html; charset=utf-8'
            self.response.write('Hello, ' + user.nickname())
        else:
            self.redirect(users.create_login_url(self.request.uri))



app = webapp2.WSGIApplication([
    ('/', LoginPage)]
    , debug=True)