import os
import webapp2
import jinja2
import hashlib
import re
import random
import string
import json
import datetime
import cgi
import urllib
import csv
import calendar
from google.appengine.api import mail
from google.appengine.ext import ndb
from google.appengine.api import images
from google.appengine.api import search
from google.appengine.api import urlfetch
from google.appengine.ext import blobstore

template_dir = os.path.join(os.path.dirname(__file__), 'html')
jinja_env = jinja2.Environment(autoescape = True,
                               loader = jinja2.FileSystemLoader(template_dir))

class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)
    def render_html(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)
    def email(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)
    def render(self, template, **kw):
        self.write(self.render_html(template, **kw))
    def valid_cookie(self):
        cookie = self.request.cookies.get('name')
        if cookie:
            user_id = cookie.split('|')[0]
            if user_id.isdigit():
                user = LogIn.get_by_id(int(user_id))
                if user and valid_id(cookie, user.pw_hash):
                    return user
        else: None
    def set_cookie(self, user_id, pw_hash):
        cookie = make_id_hash(user_id, pw_hash)
        self.response.headers.add_header('Set-Cookie', 'name=%s; Path=/' % cookie)            

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

def rescale(img_data, width, height, halign='middle', valign='middle'):
    image = images.Image(img_data)
    desired_wh_ratio = float(width) / float(height)
    wh_ratio = float(image.width) / float(image.height)
    if desired_wh_ratio > wh_ratio:
        image.resize(width=width)
        image.execute_transforms()
        trim_y = (float(image.height - height) / 2) / image.height
        if valign == 'top':
            image.crop(0.0, 0.0, 1.0, 1 - (2 * trim_y))
        elif valign == 'bottom':
            image.crop(0.0, (2 * trim_y), 1.0, 1.0)
        else:
            image.crop(0.0, trim_y, 1.0, 1 - trim_y)
    else:
        image.resize(height=height)
        image.execute_transforms()
        trim_x = (float(image.width - width) / 2) / image.width
        if halign == 'left':
            image.crop(0.0, 0.0, 1 - (2 * trim_x), 1.0)
        elif halign == 'right':
            image.crop((2 * trim_x), 0.0, 1.0, 1.0)
        else:
            image.crop(trim_x, 0.0, 1 - trim_x, 1.0)
    return image.execute_transforms()    
    
# Google App Engine DataStore
class Rating(ndb.Model):
    total = ndb.IntegerProperty (indexed = False)
    number = ndb.IntegerProperty (indexed = False)
    average = ndb.FloatProperty (indexed = False)

class Menu(ndb.Model):
    chef = ndb.KeyProperty (indexed = True, required = True)
    title = ndb.StringProperty (indexed = True)
    active = ndb.BooleanProperty (default = False)
    photo = ndb.BlobProperty (indexed = False)
    category = ndb.StringProperty (indexed = True)
    ingredients = ndb.StringProperty (indexed = False)
    serving = ndb.IntegerProperty (indexed = True)
    price = ndb.FloatProperty (indexed = True)
    rating = ndb.StructuredProperty (Rating, indexed = False)
        
class Rate(ndb.Model):
    professional = ndb.IntegerProperty (indexed = False)
    quality = ndb.IntegerProperty (indexed = False)
    overall = ndb.IntegerProperty (indexed = True)
    review = ndb.StringProperty (indexed = False)
    comment = ndb.StringProperty (indexed = False)
    created = ndb.DateTimeProperty (auto_now_add = True)

class Messages(ndb.Model):
    message = ndb.StringProperty (required = True)
    created = ndb.DateTimeProperty (auto_now_add = True)

class Address(ndb.Model):
    type = ndb.StringProperty (indexed = True)
    street = ndb.StringProperty (indexed = False)
    city = ndb.StringProperty (indexed = False)
    state = ndb.StringProperty (indexed = False)
    zipcode = ndb.StringProperty (indexed = False)
    country = ndb.StringProperty (default = "USA")

def get_zipcode(address):
    address = address.replace(" ","+")
    url = "http://maps.googleapis.com/maps/api/geocode/json?address=" + address
    result = urlfetch.fetch(url)
    data = json.loads(result.content)
    components = data['results'][0]['address_components']
    types = ['postal_code']
    zipcode = filter(lambda x: len(set(x['types']).intersection(types)), components)
    return zipcode[0]['long_name']

def zipcodes_around(zipcode, radius):
    api = "91SPRAid1mnulpdj0VuuwEjZpaXz5kWelO4domrqIPV4e8ne4SJBw2AWdyviSsxe"
    url = "https://www.zipcodeapi.com/rest/"+api+"/radius.json/"+str(zipcode)+"/"+str(radius)+"/mile"
    result = urlfetch.fetch(url)
    data = json.loads(result.content)
    zipcodes = []
    for i in range(0,len(data['zip_codes'])):
        zipcodes.append(data['zip_codes'][i]['zip_code'])
    return zipcodes

class Jobs(ndb.Model):
    client = ndb.KeyProperty (indexed = True)
    client_rating = ndb.StructuredProperty (Rate, indexed = False)
    chef = ndb.KeyProperty (indexed = True)
    chef_name = ndb.StringProperty (indexed = False)
    chef_rating = ndb.StructuredProperty (Rate, indexed = False)
    how = ndb.StringProperty (indexed = False)
    purchase = ndb.StringProperty (indexed = False)
    hours = ndb.IntegerProperty (indexed = False)
    items = ndb.KeyProperty (indexed = True, repeated = True)
    item_names = ndb.StringProperty (indexed = True, repeated = True)
    created = ndb.DateTimeProperty (auto_now_add = True)
    schedule = ndb.DateTimeProperty (indexed = True)
    propose = ndb.DateTimeProperty (indexed = True)
    phone = ndb.StringProperty (indexed = False)
    address = ndb.StructuredProperty (Address, indexed = False)
    messages = ndb.StructuredProperty (Messages, repeated = True)
    guests = ndb.IntegerProperty (indexed = False)
    price = ndb.FloatProperty (indexed = False)
    cost = ndb.FloatProperty (indexed = False)
    estimate = ndb.FloatProperty (indexed = False)
    supplies = ndb.FloatProperty (indexed = False)
    earning = ndb.FloatProperty (indexed = False)
    tip = ndb.FloatProperty (indexed = False)
    fee = ndb.FloatProperty (indexed = False)
    tax = ndb.FloatProperty (indexed = False)
    total = ndb.FloatProperty (indexed = False)
    submitted = ndb.BooleanProperty (default = False)
        
class LogIn(ndb.Model):
    user_key = ndb.KeyProperty (indexed = True)
    chef_key = ndb.KeyProperty (indexed = True)    
    first_name = ndb.StringProperty (required = True)
    last_name = ndb.StringProperty (required = True)
    email = ndb.StringProperty (required = True)
    pw_hash = ndb.StringProperty (required = True)
    created = ndb.DateTimeProperty (auto_now_add = True)
    activate = ndb.StringProperty (required = True)
    active = ndb.BooleanProperty (default = False)
    @classmethod
    def by_email(cls, email):
        u = LogIn.query(LogIn.email == email).get()
        return u
        
class Users(ndb.Model):
    login_key = ndb.KeyProperty (indexed = True)
    chef_key = ndb.KeyProperty (indexed = True)    
    first_name = ndb.StringProperty (required = True)
    last_name = ndb.StringProperty (required = True)
    sex = ndb.StringProperty (indexed = False, choices=['','male', 'female'], default = '')
    photo = ndb.BlobProperty (indexed = False)
    addresses = ndb.StructuredProperty (Address, repeated = True)
    number = ndb.StringProperty (indexed = False, default = '')
    phone_verified = ndb.BooleanProperty (default = False)
    text = ndb.BooleanProperty (indexed = False, default = False)
    dob = ndb.DateProperty (indexed = False)
    id_photo = ndb.BlobProperty (indexed = False)
    id_exp = ndb.DateProperty (indexed = True)
    id_verified = ndb.BooleanProperty (default = False)
    chef = ndb.BooleanProperty (default = False)
    jobs = ndb.KeyProperty (repeated = True, indexed = True)
    
class Chef(ndb.Model):
    login_key = ndb.KeyProperty (indexed = True)
    user_key = ndb.KeyProperty (indexed = True)
    first_name = ndb.StringProperty (required = True)
    last_name = ndb.StringProperty (required = True)
    description = ndb.StringProperty (indexed = False, required = True)
    address = ndb.StructuredProperty (Address, indexed = False)
    number = ndb.StringProperty (indexed = False)
    phone_verified = ndb.BooleanProperty (default = False)
    text = ndb.BooleanProperty (indexed = False, default = False)
    school = ndb.StringProperty (indexed = True)
    experience = ndb.IntegerProperty (indexed = True)
    hour = ndb.IntegerProperty (indexed = True)
    day = ndb.IntegerProperty (indexed = True)
    rate = ndb.BooleanProperty (default = False)
    orders = ndb.BooleanProperty (default = False)
    delivery = ndb.BooleanProperty (default = False)
    athome = ndb.BooleanProperty (default = False)
    teach = ndb.BooleanProperty (default = False)
    radius = ndb.IntegerProperty (default = 5)
    background = ndb.BooleanProperty (default = False)
    id_verified = ndb.BooleanProperty (indexed = False)
    id_exp = ndb.DateProperty (indexed = True)
    photo = ndb.BlobProperty (indexed = False)
    rating = ndb.StructuredProperty (Rating, indexed = True)
    cuisines = ndb.StringProperty (repeated = True)
    menu = ndb.KeyProperty (indexed = True, repeated = True)
    jobs = ndb.KeyProperty (repeated = True, indexed = True)
    earnings = ndb.FloatProperty (indexed = False)

class Chefs(ndb.Model):
    zipcode = ndb.IntegerProperty (indexed = True)
    chef = ndb.KeyProperty (repeated = True, indexed = True)
    @classmethod
    def by_zipcode(cls, zipcode):
        chefs = Chefs.query(Chefs.zipcode == zipcode).get()
        return chefs
    
class Photos(ndb.Model):
    photo = ndb.BlobProperty (required = True)
    
class Upload(Handler):
    def get(self):
        self.write('<form enctype="multipart/form-data" method="POST"><input type="radio" ' +
                  'name="type" value="photo">Photo<input type="radio" name="type"' +
                   'value="worksheet">Worksheet<br>Upload File: <input type="file"' +
                   'name="file"><br><input type="submit" name="submit" value="Upload"></form>')
    def post(self):
        t = self.request.get('type')
        f = self.request.get('file')
        if t == 'photo':
            new = Photos(photo=f)
            new.put()
            self.write('Done!')
        else:
            csv_f = csv.reader(f.split('\n'), delimiter=',')
            self.write('<h2>File contains:<h2>')
            for row in csv_f:
                zipcode, city, state, lat, lng = row
                self.write('%s, %s %s = %s, %s <br>' % (city, state, zipcode, lat, lng))
                localchefs = Chefs(city=city, state=state, zipcode=int(zipcode), lat=float(lat), lng=float(lng))
                localchefs.put()
    
# Securing Passwords
support = "Chefs 4 Me Support <contact@chefs4me.com>"
def make_salt():
    return ''.join(random.choice(string.letters) for x in xrange(5))
def make_pw_hash(activate, pw, salt = ""):
    if salt == "":
        salt = make_salt()
    h = hashlib.sha256(activate + pw + salt).hexdigest()
    return '%s,%s' % (salt, h)
def valid_pw(activate, password, h):
    salt = h.split(',')[0]
    return h == make_pw_hash(activate, password, salt)
def users_key(group = 'default'):
    return ndb.Key.from_path('users', group)

# Making and validating Cookies
def make_id_hash(user_id, pw):
    salt = pw.split(',')[-1]
    h = hashlib.sha256(user_id + salt).hexdigest()
    return '%s|%s' % (user_id, h)
def valid_id (cookie, pw):
    user_id = cookie.split('|')[0]
    verify = make_id_hash(user_id, pw)
    return verify == cookie

# Start Page
class About(Handler):
    def render_new(self, email="", error=""):
        self.render('0.about.html', email=email, error=error)
    def get(self):
        self.render_new()
    def post(self):
        email = self.request.get('email').lower()
        password = self.request.get('password')
        user = LogIn.by_email(email)
        if email and user and user.active and valid_pw(user.activate, password, user.pw_hash):
            self.set_cookie(str(user.key.id()), user.pw_hash)
            self.redirect('/chefs')
        elif user and (user.active == False):
            self.redirect('/activate')
        else:
            self.render_new(email, "Invalid email and/or password.")
#class About(Handler):
#    def render_new(self, email="", error="", zipcode="90211"):
#        chefs = Chefs.by_zipcode(int(zipcode))
#        localchefs = []
#        try:
#            for chef in chefs.chef:
#                local = Chef.get_by_id(chef.id())
#                local.photo = rescale(local.photo, 250, 250)
#                localchefs.append(local)
#                message = ''
#        except:
#            message = "Sorry, I could not find any personal chefs around the "+str(zipcode)+" zip code. If you know of any, encourage them to signup for Cook 4 Me." 
#        self.render('0.about.html', email=email, error=error, base='unlogged.html', chefs=localchefs, zipcode=zipcode, message=message)
#    def get(self):
#        self.render_new()
#    def post(self):
#        change = self.request.get('change', None)
#        login = self.request.get('login', None)
#        if change:
#            zipcode = self.request.get('zipcode')
#            address = self.request.get('address')
#            try:
#                int(address)
#                zipcode = address
#            except: error = 'Not a zipcode.'
#            try: zipcode = get_zipcode(address)
#            except: error = 'Not an address.'
#            self.render_new(zipcode)
#        if login:
#            email = self.request.get('email').lower()
#            password = self.request.get('password')
#            user = LogIn.by_email(email)
#            if email and user and user.active and valid_pw(user.activate, password, user.pw_hash):
#                self.set_cookie(str(user.key.id()), user.pw_hash)
#                self.redirect('/chefs')
#            elif user and (user.active == False):
#                self.redirect('/activate')
#            else:
#                self.render_new(email, "Invalid email and password.")
                
# Signs In User
class SignUp(Handler):
    def render_new(self, first_name = "", last_name = "", email = "", error_email=""):
        self.render('0.signup.html', first_name=first_name, last_name=last_name, email=email, error_email=error_email)
    def get(self):
        self.render_new()
    def post(self):
        first_name = self.request.get('first_name')
        last_name = self.request.get('last_name')
        email = self.request.get('email').lower()
        password = self.request.get('password')
        if LogIn.by_email(email):
            error_email = "Looks like your twin already registered you."
            self.render_new(first_name, last_name, email, error_email)
        else:
            subject = "Confirm your registration"
            activate = str(random.randint(10000, 99999))
            body = self.email('e.activate.txt', first_name=first_name, activate=activate)
            mail.send_mail(support, email, subject, body)
            pw_hash = make_pw_hash(activate, password)
            newlogin = LogIn(email=email, pw_hash=pw_hash, activate=activate, first_name=first_name, last_name=last_name)
            newlogin.put()
            self.set_cookie(str(newlogin.key.id()), pw_hash)
            self.redirect('/activate')

# Activates New Users
class Activate(Handler):
    def render_new(self, email="", error=""):
        self.render('0.activate.html', email=email, error=error)
    def get(self):
        self.render_new("", "Please check your email for your activation code.")
    def post(self):
        email = self.request.get('email').lower()
        password = self.request.get('password')
        activate = self.request.get('activate')
        login = LogIn.by_email(email)
        if login and (login.activate == activate) and valid_pw(login.activate, password, login.pw_hash):
            login.active = True
            newuser = Users(first_name=login.first_name, last_name=login.last_name, login_key=login.key)
            x = Photos.get_by_id(5066549580791808)
            newuser.photo = rescale(x.photo, 400, 400)
            newuser.addresses.append(Address(type='Home'))
            newuser.put()
            login.user_key = newuser.key
            login.put()
            self.set_cookie(str(login.key.id()), login.pw_hash)
            self.redirect('/profile')
        elif login and (login.activate != activate):
            self.render_new(email, "Please enter the activation code from you email.")
        else:
            self.render_new(email, "Invalid email and password.")

# Emails User with Forgotten Password
class Password(Handler):
    def render_new(self, email="", error=""):
        self.render('0.password.html', email=email, error=error)
    def get(self):
        self.render_new()
    def post(self):
        email = self.request.get('email').lower()
        user = LogIn.by_email(email)
        if user:
            body = self.email('e.password.txt', first_name=user.first_name, activate=user.activate)
            subject = "Reset Password"
            mail.send_mail(support, email, subject, body)
            self.redirect('/reset')
        else:
            self.render_new(email, "I didn't find that email.  Could you retype it?")

# Creates New Password with Code sent to Email
class Reset(Handler):
    def render_new(self, email="", error=""):
        self.render('0.reset.html', email=email, error=error)
    def get(self):
        self.render_new()
    def post(self):
        email = self.request.get('email').lower()
        activate = self.request.get('code')
        password = self.request.get('password')
        user = LogIn.by_email(email)
        if user and (activate == user.activate):
            user.activate = str(random.randint(10000, 99999))
            user.pw_hash = make_pw_hash(user.activate, password)
            user.put()
            self.redirect('/chefs')
        else:
            self.render_new(email, "My records don't match the email and reset code you entered.")     

# Local Chefs: This should bring me to my welcome page with different things for users to do.
class LocalChefs(Handler):
    def render_new(self, zipcode):
        chefs = Chefs.by_zipcode(int(zipcode))
        localchefs = []
        try:
            for chef in chefs.chef:
                local = Chef.get_by_id(chef.id())
                local.photo = rescale(local.photo, 250, 250)
                localchefs.append(local)
                message = ''
        except:
            message = "Sorry, I could not find any personal chefs around the "+str(zipcode)+" zip code. If you know of any, encourage them to signup for Cook 4 Me." 
        self.render('1.chefs.html', chefs=localchefs, zipcode=zipcode, message=message)
    def get(self):
        login = self.valid_cookie()
        user = Users.get_by_id(login.user_key.id())
        zipcode = user.addresses[0].zipcode
        self.render_new(zipcode)
    def post(self):
        address = self.request.get('address')
        zipcode = self.request.get('zipcode')
        try:
            int(address)
            zipcode = address
        except: error = 'Not a zipcode.'
        try: zipcode = get_zipcode(address)
        except: error = 'Not an address.'
        self.render_new(zipcode)

class Order(Handler):
    def get(self):
        login = self.valid_cookie()
        user = Users.get_by_id(login.user_key.id())
        chef_key = urlsafe=self.request.get('chef')
        chef = Chef.get_by_id(int(chef_key))
        items = []
        for item in chef.menu:
            i = Menu.get_by_id(item.id())
            if i: items.append(i)
        self.render('1.menu.html', chef=chef, user=user, items=items)
    def post(self):
        login = self.valid_cookie()
        user = Users.get_by_id(login.user_key.id())
        chef_key = self.request.get('chef')
        chef = Chef.get_by_id(int(chef_key))
        job = Jobs(client = user.key, chef = chef.key)
        job.chef_name = chef.last_name
        job.how = self.request.get('how')
        items = self.request.get_all('item')
        cost_by_item = 0
        for item in items:
            food = Menu.get_by_id(int(item))
            job.item_names.append(food.title)
            job.items.append(food.key)
            cost_by_item += food.price
        if job.how == "day":
            job.purchase = self.request.get('day_purchase')
            job.guests = int(self.request.get('guests'))
            job.price = chef.day
        elif job.how == "hour":
            job.purchase = self.request.get('hour_purchase')
            job.hours = int(self.request.get('hours'))
            job.guests = int(self.request.get('guests'))
            job.price = chef.hour * job.hours
        elif job.how == "byitem":
            job.purchase = self.request.get('byitem')
            job.price = cost_by_item
        job.fee = round(job.price * .09, 2)
        job.total = round(job.price + job.fee, 2)
        dt = self.request.get('date') + ' ' + self.request.get('time')
        job.propose = datetime.datetime.strptime(dt, "%Y-%m-%d %H:%M")
        job.phone = self.request.get('phone')
        address = self.request.get('addresses')
        title = self.request.get('title')
        street, city, = self.request.get('street'), self.request.get('city')
        state, zipcode = self.request.get('state'), self.request.get('zipcode')
        job.address = Address(type=title, street=street, city=city, state=state, zipcode=zipcode)
        if title:
            if address == "New Address":
                user.addresses.append(job.address)
            else:
                for i in range(0, len(user.addresses)):
                    if address == user.addresses[i].type:
                        if user.addresses[i] != job.address:
                            user.addresses[i] = job.address
        job.put()
        user.jobs.append(job.key)
        user.put()
        self.redirect('/confirm?order=%s' % job.key.id())
        
class Confirm(Handler):
    def get(self):
        login = self.valid_cookie()
        user = Users.get_by_id(login.user_key.id())
        job_id = urlsafe=self.request.get('order')
        job = Jobs.get_by_id(int(job_id))
        chef = Chef.get_by_id(job.chef.id())
        items = []
        for item in job.items:
            i = Menu.get_by_id(item.id())
            if i: items.append(i)
        self.render('1.confirm.html', chef=chef, user=user, items=items, job=job)
    def post(self):
        login = self.valid_cookie()
        user = Users.get_by_id(login.user_key.id())
        job_id = self.request.get('job_id')
        job = Jobs.get_by_id(int(job_id))
        custom = self.request.get('custom')
        new = Messages(message = custom)
        job.messages.append(new)
        job.submitted = True
        job.put()
        chef = Chef.get_by_id(job.chef.id())
        chef.jobs.append(job.key)
        chef.put()
        #send chef email and/or text
        self.render('1.complete.html', job=job, chef=chef)
        
class InBox(Handler):
    def get(self):
        login = self.valid_cookie()
        user = Users.get_by_id(login.user_key.id())
        jobs = []
        for job in user.jobs:
            j = Jobs.get_by_id(job.id())
            if j: jobs.append(j)        
        self.render('2.inbox.html', user=user, jobs=jobs)

# Edit Chef Profile
class ChefProfile(Handler):
    def get(self):
        login = self.valid_cookie()
        user = Users.get_by_id(login.user_key.id())
        address, phone = user.addresses[0], user.number
        chef = Chef.get_by_id(login.chef_key.id())
        self.render('3.chef.html', chef = chef, address = address, phone = phone)
    def post(self):
        login = self.valid_cookie()
        chef = Chef.get_by_id(login.chef_key.id())
        photo = self.request.get('photo')
        if photo: 
            photo = rescale(photo, 250, 250)
            chef.photo = photo
        chef.description = self.request.get('description')
        chef.school = self.request.get('school')
        chef.experience = int(self.request.get('experience'))
        chef.hour = int(self.request.get('hour'))
        chef.day = int(self.request.get('day'))
        chef.rate = self.request.get('rate') != ''
        chef.orders = self.request.get('orders') != ''        
        chef.delivery = self.request.get('delivery') != ''
        chef.athome = self.request.get('home') != ''
        chef.teach = self.request.get('teach') != ''
        chef.cuisines = self.request.get_all('cuisines')
        chef.number = self.request.get('phone')
        chef.text = self.request.get('text') != ''
        street, city, = self.request.get('street'), self.request.get('city')
        state, zipcode = self.request.get('state'), self.request.get('zipcode')
        work = Address(type='Work', street=street, city=city, state=state, zipcode=zipcode)
        radius = int(self.request.get('raidus'))
        if not(chef.address) or (chef.radius != radius) or (chef.address.zipcode != work.zipcode):
            try: oldzips = zipcodes_around(chef.address.zipcode, chef.radius)
            except: oldzips = []
            newzips = zipcodes_around(work.zipcode, radius)
            for zipcode in oldzips:
                if zipcode not in newzips:
                    old = Chefs.by_zipcode(int(zipcode))
                    old.chef.remove(chef.key)
                    old.put()
            for zipcode in newzips:
                if zipcode not in oldzips:
                    zips = Chefs.by_zipcode(int(zipcode))
                    if zips:
                        zips.chef.append(chef.key)
                        zips.put()
                    else:
                        new = Chefs(zipcode=int(zipcode))
                        new.chef.append(chef.key)
                        new.put()
        chef.radius = radius
        chef.address = work
        chef.put()
        self.redirect('/preview')
        
# Edit Menu
class EditMenu(Handler):
    def get(self):
        login = self.valid_cookie()
        chef = Chef.get_by_id(login.chef_key.id())
        items = []
        for item in chef.menu:
            i = Menu.get_by_id(item.id())
            if i: items.append(i)
        self.render('3.edit.html', user = chef, items = items)
    def post(self):
        login = self.valid_cookie()
        chef = Chef.get_by_id(login.chef_key.id())
        ids = self.request.get_all('item_id')
        photos = self.request.get_all('photo')
        titles = self.request.get_all('title')
        prices = self.request.get_all('price')
        servings = self.request.get_all('serving')
        categories = self.request.get_all('category')
        ingredients = self.request.get_all('ingredients')
        deleted = self.request.get('deleted').split(',')
        count = 0;
        added = False
        for item in ids:
            if item:
                old = Menu.get_by_id(int(item))
                changed = False
                if photos[count]:
                    photos[count] = rescale(photos[count], 300, 300)
                    old.photo = photos[count]
                    changed = True
                if old.title != titles[count]:
                    old.title = titles[count]
                    changed = True
                if old.price != float(prices[count]):
                    old.price = float(prices[count])
                    changed = True
                if old.serving != int(servings[count]):
                    old.serving = int(servings[count])
                    changed = True
                if old.category != categories[count]:
                    old.category = categories[count]
                    changed = True
                if old.ingredients != ingredients[count]:
                    old.ingredients = ingredients[count]
                    changed = True
                if changed:
                    old.put()
            else:
                if not prices[count]: prices[count] = 0
                if not servings[count]: servings[count] = 0
                new = Menu(chef=chef.key, title=titles[count], 
                           price=float(prices[count]), serving=int(servings[count]),
                           category=categories[count], ingredients=ingredients[count])
                if photos[count]:
                    photos[count] = rescale(photos[count], 300, 300)
                    new.photo = photos[count]
                else:
                    photo = Photos.get_by_id(5066549580791808)
                    new.photo = rescale(photo.photo, 300, 300)
                new.put()
                chef.menu.append(new.key)
                added = True
            count +=1
        deleted.remove('')
        for d in deleted:
            if d:
                item = Menu.get_by_id(int(d))
                chef.menu.remove(item.key)
                item.key.delete()
                added = True
        if added: chef.put()
        self.redirect('/preview')

class Preview(Handler):
    def get(self):
        login = self.valid_cookie()
        chef = Chef.get_by_id(login.chef_key.id())
        items = []
        for item in chef.menu:
            i = Menu.get_by_id(item.id())
            if i: items.append(i)
        self.render('3.preview.html', chef = chef, items = items)
        
# Updates Profile: To-Do: verify text, reviews, rating stars, javascript not to submit invalid inputs
class Profile(Handler):
    def get(self):
        login = self.valid_cookie()
        user = Users.get_by_id(login.user_key.id())
        self.render('4.profile.html', user = user)
    def post(self):
        login = self.valid_cookie()
        user = Users.get_by_id(login.user_key.id())
        photo = self.request.get('photo')
        if photo: 
            photo = rescale(photo, 400, 400)
            user.photo = photo
        id_photo = self.request.get('id')
        user.first_name = self.request.get('first_name')
        user.last_name = self.request.get('last_name')
        if id_photo:
            subject = "Confirm %s ID" % user.first_name
            body = self.email('e.id.txt', first_name=first_name, activate=activate)
            mail.send_mail(user.email, support, subject, body)
            user.id_photo = id_photo
        date_entry = self.request.get('dob')
        if date_entry:
            year, month, day = map(int, date_entry.split('-'))
            user.id_exp = datetime.date(year, month, day)
            user.dob = datetime.date(year, month, day)
        user.sex = self.request.get('sex').lower()
        user.number = self.request.get('phone')
        user.text = self.request.get('text') != ''
        street = self.request.get('street')
        city = self.request.get('city')
        state = self.request.get('state')
        zipcode = self.request.get('zipcode')
        home = Address(type='Home', street=street, city=city, state=state, zipcode=zipcode, country='USA')
        user.addresses[0] = home
        if (self.request.get('chef')== 'yes'): 
            user.chef = True
            if not user.chef_key:
                new = Chef(user_key = user.key, first_name = user.first_name,
                           login_key = login.key, last_name = user.last_name)
                new.photo = user.photo
                new.put()
                user.chef_key = new.key
                login.chef_key = new.key
                login.put()
            else:
                chef = Chef.get_by_id(user.chef_key.id())
                chef.first_name, chef.last_name = user.first_name, user.last_name
                chef.put()
        else: 
            user.chef = False
        user.put()
        self.redirect('/profile')
        
class Payment(Handler):
    def get(self):
        login = self.valid_cookie()
        user = Users.get_by_id(login.user_key.id())
        photo = "/img?img_id=%s" % (user.key.urlsafe())
        self.render('4.payment.html', photo=photo)


# Changes Email & Password  
class Security(Handler):
    def render_new(self, login, message="", pw_message=""):
        photo = Users.get_by_id(login.user_key.id())
        photo = "/img?img_id=%s" % (photo.key.urlsafe())
        self.render('4.security.html', photo=photo, email=login.email, message=message, pw_message=pw_message)
    def get(self):
        login = self.valid_cookie()
        self.render_new(login)
    def post(self):
        login = self.valid_cookie()
        update_email = self.request.get('update_email', None)
        change_pw = self.request.get('change_password', None)
        if update_email:
            email = self.request.get('email')
            if LogIn.by_email(email):
                message = "Email NOT updated: Looks like your twin already registered you."
            else:
# Send Email to old email address of change in email address.
                login.email = email
                login.put()
                message = "Your email has been updated."
            self.render_new(login, message)
        if change_pw:
            old_pw = self.request.get('old')
            new_pw = self.request.get('password')
            if valid_pw(login.activate, old_pw, login.pw_hash):
# Send Email of change in password.
                login.pw_hash = make_pw_hash(login.activate, new_pw)
                login.put()
                self.set_cookie(str(login.key.id()), login.pw_hash)
                pw_message = "Your Password has been changed."
            else:
                pw_message = "Your Old Password does NOT match our records!"
            self.render_new(login, "", pw_message)

# Log Out: Need to create link to help me log out.
class LogOut(Handler):
    def get(self):
        self.response.headers.add_header('Set-Cookie', 'name=; Path=/')            
        self.redirect('/')

class Image(webapp2.RequestHandler):
    def get(self):
        user_key = ndb.Key(urlsafe=self.request.get('img_id'))
        user = user_key.get()
        self.response.headers['Content-Type'] = 'image/png'
        self.response.out.write(user.photo)
        
app = webapp2.WSGIApplication([('/', About),
                               ('/signup', SignUp),
                               ('/activate', Activate),
                               ('/password', Password),
                               ('/reset', Reset),
                               ('/chefs', LocalChefs),
                               ('/order', Order),
                               ('/confirm', Confirm),
                               ('/inbox', InBox),
                               ('/chef', ChefProfile),
                               ('/menu', EditMenu),
                               ('/preview', Preview),
                               ('/profile', Profile),
                               ('/payment', Payment),
                               ('/security', Security),
                               ('/logout', LogOut),
                               
                               ('/upload', Upload),
                               ('/img', Image)],
                              debug = True)