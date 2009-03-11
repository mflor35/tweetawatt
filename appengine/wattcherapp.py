import cgi, datetime

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext import db

import gviz_api

class Powerusage(db.Model):
  author = db.UserProperty()           # the user
  sensornum = db.IntegerProperty()     # can have multiple sensors
  watt = db.FloatProperty()          # each sending us latest Watt measurement
  date = db.DateTimeProperty(auto_now_add=True)    # timestamp

class Sensorname(db.Model):
  author = db.UserProperty()           # the user
  sensornum = db.IntegerProperty()     # can have multiple sensors
  sensorname = db.StringProperty()
  
class UTC(datetime.tzinfo):
    """UTC"""

    def utcoffset(self, dt):
        return datetime.timedelta(hours=0)
    def tzname(self, dt):
        return "UTC"
    def dst(self, dt):
        return datetime.timedelta(hours=0)
                                  
utc = UTC()

class Eastern_tzinfo(datetime.tzinfo):
 """Implementation of the eastern timezone."""
 def utcoffset(self, dt):
   return datetime.timedelta(hours=-5) + self.dst(dt)

 def _FirstSunday(self, dt):
   """First Sunday on or after dt."""
   return dt + datetime.timedelta(days=(6-dt.weekday()))

 def dst(self, dt):
   # 2 am on the second Sunday in March
   dst_start = self._FirstSunday(datetime.datetime(dt.year, 3, 8, 2))
   # 1 am on the first Sunday in November
   dst_end = self._FirstSunday(datetime.datetime(dt.year, 11, 1, 1))

   if dst_start <= dt.replace(tzinfo=None) < dst_end:
     return datetime.timedelta(hours=1)
   else:
     return datetime.timedelta(hours=0)

 def tzname(self, dt):
   if self.dst(dt) == datetime.timedelta(hours=0):
     return "EST"
   else:
     return "EDT"

est = Eastern_tzinfo()


#######################################
class DumpData(webapp.RequestHandler):
  def get(self):

    # make the user log in
    if not users.get_current_user():
        self.redirect(users.create_login_url(self.request.uri))

    self.response.out.write('<html><body>Here is all the data you have sent us:<p>')

    powerusages = db.GqlQuery("SELECT * FROM Powerusage WHERE author = :1 ORDER BY date", users.get_current_user())

    for powerused in powerusages:
        if powerused.sensornum:
           currnamequery = db.GqlQuery("SELECT * FROM Sensorname WHERE author = :1 AND sensornum = :2", account, powerused.sensornum)
           name = currnamequery.get()
            
           self.response.out.write('<b>%s</b>\'s sensor #%d' %
                                  (powerused.author.nickname(), powerused.sensornum))
        else:
          self.response.out.write('<b>%s</b>' % powerused.author.nickname())

        self.response.out.write(' used: %f Watts at %s<p>' % (powerused.watt, powerused.date))
    self.response.out.write("</body></html>")

#########################################################################################

class MainPage(webapp.RequestHandler):
  def get(self):
    self.response.out.write('<html><body>Welcome to Wattcher!<p>Here are the last 10 datapoints:<p>')

    powerusages = db.GqlQuery("SELECT * FROM Powerusage ORDER BY date DESC LIMIT 10")
   
    for powerused in powerusages:
        if powerused.sensornum:
          currnamequery = db.GqlQuery("SELECT * FROM Sensorname WHERE author = :1 AND sensornum = :2", powerused.author, powerused.sensornum)
          currname = currnamequery.get()

          name = "sensor #"+str(powerused.sensornum)
          if currname:
            name = currname.sensorname

          self.response.out.write('<b>%s</b>:  %s ' %
                                  (powerused.author.nickname(), name))
        else:
          self.response.out.write('<b>%s</b>' % powerused.author.nickname())

        newdate = powerused.date.replace(tzinfo=utc).astimezone(est)
        
        self.response.out.write(' used: %f Watts at %s<p>' % (powerused.watt, newdate))
    self.response.out.write("</body></html>")

class Configure(webapp.RequestHandler):
  def get(self):
    # make the user log in if no user name is supplied
    if self.request.get('user'):
      account = users.User(self.request.get('user'))
    else:
       if not users.get_current_user():
         self.redirect(users.create_login_url(self.request.uri))
       account = users.get_current_user()


    # find all the sensors up to #10
    self.response.out.write('<html><body>Set up your sensornode names here:<p>')
    sensorset = []
    for i in range(10):
      c = db.GqlQuery("SELECT * FROM Powerusage WHERE author = :1 and sensornum = :2", users.get_current_user(), i)
      if c.get():
        sensorset.append(i)

    self.response.out.write('<form action="/config" method="get">')
    for sensor in sensorset:
      name = ""
      currnamequery = db.GqlQuery("SELECT * FROM Sensorname WHERE author = :1 AND sensornum = :2", users.get_current_user(), sensor)
      currname = currnamequery.get()
    
      # first see if we're setting it!
      if self.request.get('sensornum'+str(sensor)):
        name = self.request.get('sensornum'+str(sensor))
        if not currname:
          currname = Sensorname()  # create a new entry
          currname.sensornum = sensor
          currname.author = users.get_current_user()
        currname.sensorname = name
        currname.put()
      else:
      # we're not setting it so fetch current entry
        if currname:
           name = currname.sensorname
          
      self.response.out.write('Sensor #'+str(sensor)+': <input type="text" name="sensornum'+str(sensor)+'" value="'+name+'"></text><p>')
      
    self.response.out.write("""<div><input type="submit" value="Change names"></div>
      </form>
      </body>
      </html>""")

#########################################################################################

class VisualizeAll(webapp.RequestHandler):
  def get(self):

    # make the user log in if no user name is supplied
    if self.request.get('user'):
      account = users.User(self.request.get('user'))
    else:
       if not users.get_current_user():
         self.redirect(users.create_login_url(self.request.uri))
       account = users.get_current_user()

    self.response.out.write('''
<h2>Power usage over the last hour:</h2>
<iframe src ="graph?user=adawattz@gmail.com&bhours=1" frameborder="0" width="100%" height="300px">
  <p>Your browser does not support iframes.</p>
</iframe>

<h2>Power usage over the last day:</h2>
<iframe src ="graph?user=adawattz@gmail.com&bhours=24"  frameborder="0" width="100%" height="300px">
  <p>Your browser does not support iframes.</p>
</iframe>

<h2>Power usage over the last week:</h2>
<iframe src ="graph?user=adawattz@gmail.com&bhours=168"  frameborder="0"  width="300%" height="500px">
  <p>Your browser does not support iframes.</p>
</iframe>

      ''')
    

#########################################################################################

class Visualize(webapp.RequestHandler):
  def get(self):

    # make the user log in if no user name is supplied
    if self.request.get('user'):
      account = users.User(self.request.get('user'))
    else:
       if not users.get_current_user():
         self.redirect(users.create_login_url(self.request.uri))
       account = users.get_current_user()

         
    historytimebegin = 24 # assume 24 hours
    if self.request.get('bhours'):
      historytimebegin = int(self.request.get('bhours'))


    historytimeend = 0 # assume 0 hours ago
    if self.request.get('ehours'):
      historytimeend = int(self.request.get('ehours'))

    # get the first part, headers, out
    self.response.out.write('''
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta http-equiv="content-type" content="text/html; charset=utf-8" />
  <title>Google Visualization API Sample</title>
  <script type="text/javascript" src="http://www.google.com/jsapi"></script>
  <script type="text/javascript">
    google.load("visualization", "1", {packages: ["annotatedtimeline"]});

    function drawVisualizations() {
    ''')

    # create our visualization
    self.response.out.write('''new google.visualization.Query("http://wattcher.appspot.com/visquery.json?user='''+account.email()+'''&bhours='''+str(historytimebegin)+'''").send(
          function(response) {
            new google.visualization.AnnotatedTimeLine(
                document.getElementById("visualization")).
                draw(response.getDataTable(), {"displayAnnotations": true});
          });
          ''')
                     
    self.response.out.write('''}
    
    google.setOnLoadCallback(drawVisualizations);
  </script>
</head>
<body style="font-family: Arial;border: 0 none;">
<div id="visualization" style="width: 800px; height: 250px;"></div>
</body> 
</html>''')
    # create visualization #1, last hour
    
#########################################################################################

class JSONout(webapp.RequestHandler):
  def get(self):

    # make the user log in if no user name is supplied
    if self.request.get('user'):
      account = users.User(self.request.get('user'))
    else:
       if not users.get_current_user():
         self.redirect(users.create_login_url(self.request.uri))
       account = users.get_current_user()
         
    # assume we want 24 hours of data
    historytimebegin = 24 
    if self.request.get('bhours'):
      historytimebegin = int(self.request.get('bhours'))


    # assume we want data starting from 0 hours ago
    historytimeend = 0 
    if self.request.get('ehours'):
      historytimeend = int(self.request.get('ehours'))

    # data format for JSON happiness 
    datastore = []
    columnnames = ["date"]
    columnset = set(columnnames)
    description ={"date": ("datetime", "Date")}
      
    # the names of each sensor, if configured
    sensornames = [ None ] * 10

    # we cant grab more than 1000 datapoints, thanks to free-app-engine restriction
    # thats about 3 sensors's worth in one day
    # so we will restrict to only grabbing 12 hours of data at a time, about 7 sensors worth
    
    while (historytimebegin > historytimeend):
      if (historytimebegin - historytimeend) > 12:
        timebegin = datetime.timedelta(hours = -historytimebegin)
        timeend = datetime.timedelta(hours = -(historytimebegin-12))
        historytimebegin -= 12
      else:
        timebegin = datetime.timedelta(hours = -historytimebegin)
        historytimebegin = 0
        timeend = datetime.timedelta(hours = -historytimeend)

      # grab all the sensor data for that time chunk
      powerusages = db.GqlQuery("SELECT * FROM Powerusage WHERE date > :1 AND date < :2 AND author = :3 ORDER BY date", datetime.datetime.now()+timebegin, datetime.datetime.now()+timeend, account)

      # sort them into the proper format and add sensor names from that DB if not done yet
      for powerused in powerusages:
        coln = "watts" + str(powerused.sensornum)
        entry = {"date": powerused.date.replace(tzinfo=utc).astimezone(est), coln: powerused.watt}
        if not (coln in columnset):
          columnnames.append(coln)
          columnset = set(columnnames)
          # find the sensor name, if we can
          if (len(sensornames) < powerused.sensornum) or (not sensornames[powerused.sensornum]):
            currnamequery = db.GqlQuery("SELECT * FROM Sensorname WHERE author = :1 AND sensornum = :2", account, powerused.sensornum)
            name = currnamequery.get()
            
            if not name:
              sensornames[powerused.sensornum] = "sensor #"+str(powerused.sensornum)
            else:
              sensornames[powerused.sensornum] = name.sensorname

          description[coln] = ("number", sensornames[powerused.sensornum])
          #self.response.out.write(sensornames)

        # add one entry at a time
        datastore.append(entry)
    #self.response.out.write(datastore)
    #self.response.out.write(columnnames)
    #self.response.out.write(description)
    #return

    # OK all the data is ready to go, print it out in JSON format!
    data_table = gviz_api.DataTable(description)
    data_table.LoadData(datastore)
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write(data_table.ToJSonResponse(columns_order=(columnnames),
                                    order_by="date"))



class Shortreport(webapp.RequestHandler):
  def get(self):

    # make the user log in if no user name is supplied
    if self.request.get('user'):
      account = users.User(self.request.get('user'))
    else:
       if not users.get_current_user():
         self.redirect(users.create_login_url(self.request.uri))
       account = users.get_current_user()

    # get current power usage
    currentwatts = 0
    timebegin = datetime.timedelta(minutes = -5)
    powerusages = db.GqlQuery("SELECT * FROM Powerusage WHERE date > :1 AND author = :2 ORDER BY date", datetime.datetime.now()+timebegin, account)
    for powerused in powerusages:
       currentwatts += powerused.watt
      
    # get Watthrs for today
    timebegin = datetime.timedelta(hours = -24)
    powerusages = db.GqlQuery("SELECT * FROM Powerusage WHERE date > :1 AND author = :2 ORDER BY date", datetime.datetime.now()+timebegin, account)
    todaywatthr = 0
    for powerused in powerusages:
      # add them all up, 5 watt*minute at a time!
      todaywatthr += powerused.watt/12.0
      
    # get Watthrs for yesterday
    timebegin = datetime.timedelta(hours = -48)
    timeend = datetime.timedelta(hours = -24)
    powerusages = db.GqlQuery("SELECT * FROM Powerusage WHERE date > :1 AND date < :2 AND author = :3 ORDER BY date", datetime.datetime.now()+timebegin, datetime.datetime.now()+timeend, account)
    
    yesterdaywatthr = 0
    for powerused in powerusages:
      # add them all up, 5 watt*minute at a time!
      yesterdaywatthr += powerused.watt/12.0

    self.response.out.write("Currently using %.1f Watts, %.0f Wh in last 24hr, %.0f Wh previous day - http://bit.ly/ZTUR #wattzon" % (currentwatts, todaywatthr, yesterdaywatthr))

#########################################################################################
class PowerUpdate(webapp.RequestHandler):
  def get(self):

    # make the user log in
    if not users.get_current_user():
        self.redirect(users.create_login_url(self.request.uri))

    powerusage = Powerusage()
    
    if users.get_current_user():
        powerusage.author = users.get_current_user()
    #print self.request
    if self.request.get('watt'):
        powerusage.watt = float(self.request.get('watt'))
    else:
         self.response.out.write('Couldnt find \'watt\' GET property!')
         return
    if  self.request.get('sensornum'):
        powerusage.sensornum = int(self.request.get('sensornum'))
    else:
        powerusage.sensornum = 0   # assume theres just one or something
        
    powerusage.put()
    self.response.out.write('<html><body>OK!</body></html>')

#########################################################################################
    
application = webapp.WSGIApplication(
    [('/', MainPage),
     ('/report', PowerUpdate),
     ('/visquery.json', JSONout),
     ('/graph', Visualize),
     ('/history', VisualizeAll),
     ('/tweetreport', Shortreport),
     ('/config', Configure),
     ('/dump', DumpData)],
    debug=True)

def main():
  run_wsgi_app(application)

if __name__ == "__main__":
  main()
