#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# Google
from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from google.appengine.api import urlfetch
from google.appengine.ext import db
from google.appengine.ext.webapp import template

# Youtube
import gdata.youtube.service

# Other
from BeautifulSoup import BeautifulSoup
import gaemechanize
import simplejson
import sys
import html2text
import simplejson
import datetime
import os

# Models
from models import VideoData


############################################ Main #########################################################

class MainHandler(webapp.RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, {}))

############################################ Display Mechanism ############################################   
        
class DisplayVideos(webapp.RequestHandler): 
    def get(self):
        """ 
        Displays all videos.        
        """
        videoAll = {}
        
        dataModelRetrieve = VideoData()  
        
        counter = 0
        for video in dataModelRetrieve.all():
           counter = counter+1
           
           # turn them into dictionaries
           videoInfo = eval(video.json)
           videoViews = eval(video.views)
           videoAll[counter] = { "info" : videoInfo, "views" : videoViews}
        
        result = simplejson.dumps(videoAll)
        
        self.response.headers['Content-Type'] = 'application/json'
        self.response.out.write(result)

############################################ Storing Mechanism ############################################     
        
class StoreVideos(webapp.RequestHandler):    
    def get(self):
        """ 
        Connects to DataStore model checks if any data has been stored under the same date, 
        If not gets the entries from Youtube API and stores them in that day.
        """

        # Connect to Youtube Service
        yt_service = gdata.youtube.service.YouTubeService()        
        feed = yt_service.GetMostRecentVideoFeed()       
        
        tokens = []
        dataModelRetrieve = VideoData()  
               
        # Creates Array with all elements
        for tokenid in dataModelRetrieve.all():
            tokens.append(tokenid.token)
            
        # Checks for videos and just adds the new ones
        for entry in feed.entry:
                        
            vidtoken = entry.media.player.url[31:-29] # stripping youtube + gdata path junk

            dataModelStore = VideoData(key_name=vidtoken)
            dataModelStore.token = vidtoken
            dataModelStore.json = simplejson.dumps(self.getVideoInfo(entry))
            dataModelStore.views = simplejson.dumps(self.getVideoViews(entry))
            dataModelStore.alertLevel = "initial"
            dataModelStore.put()       

        
    def getVideoInfo(self,entry):
        """ 
        Connects to Youtube API, gets the feed of most recent videos and parses each 
        entry into a dictionary.
        """
        thumbs = []

        # check if Youtube is returning all objects
        if  entry.media.title:
            title = entry.media.title.text
        else:
            title = "Couldn't retrieve title"
        if  entry.published:

            date_published = entry.published.text[0:-8] # to simplify we take out milliseconds of date published
        else:
            date_published = "Couldn't retrieve date"
        
        if entry.media.player:
            url = entry.media.player.url           
        else:
            url = "Couldn't retrieve URL"
        if entry.media.thumbnail:
            for thumbnail in entry.media.thumbnail:
                thumbs.append(thumbnail.url)
        else:
            thumbs = []
        
        # add them to a dict
        video = { "title" : title, "date_published" : date_published, "url" : url, "thumbs" : thumbs}
        
        return video

    def getVideoViews(self,entry):
        """ 
        Get video views and store them in a separate entity
        """
        
        viewsdict = {}
    
        # get current datetime
        now = datetime.datetime.now()
        nowstr = now.strftime("%Y-%m-%dT%H:%M") # youtube consistent date format
    
        if entry.statistics:
            viewcount = entry.statistics.view_count
            viewsdict[nowstr] = viewcount
        else:
            viewcount = "0"
            viewsdict[nowstr] = "0"                               
        
        return viewsdict


class MonitorVideos(webapp.RequestHandler):
    def get(self):
        """ 
        Selects videos from database and tracks their views over time
        """

        # get current datetime
        now = datetime.datetime.now()
        nowstr = now.strftime("%Y-%m-%dT%H:%M") # youtube consistent date format
        
        queryModel = VideoData.all()
                
        for video in queryModel:
           # get id
           video_k = db.Key.from_path("VideoData", video.token)
           video_o = db.get(video_k)
           
           # add new key pair to dictionary
           convertDict = eval(video_o.views)
           convertDict[nowstr] = self.getEntryData(video.token)
           
           video_o.views = simplejson.dumps(convertDict)
           video_o.put()
           #video_o.delete()

      
    def getEntryData(self,entry_id):
        """ 
        Connect to YT service and gets video viewcount 
        """

        # Connect to Youtube Service
        yt_service = gdata.youtube.service.YouTubeService()
        entry = yt_service.GetYouTubeVideoEntry(video_id=entry_id)

        if entry.statistics:
            view_count = entry.statistics.view_count
        else:
            view_count = "0"
            
        return view_count
        
        
class ScrapePage(webapp.RequestHandler):
     def get(self):

          br = gaemechanize.Browser()
          
          # Browser options
          br.set_handle_equiv(True)
          br.set_handle_gzip(True)
          br.set_handle_redirect(True)
          br.set_handle_referer(True)
          br.set_handle_robots(False)

          # User-Agent (this is cheating, ok?)
          br.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.0.1) Gecko/2008071615 Fedora/3.0.1-1.fc9 Firefox/3.0.1')]

          # The site we will navigate into, handling it's session
          br.open('http://www.youtube.com')

          # Select the first (index zero) form
          #for f in br.forms():
          #    print ''
          #    print f
 
          # Scrape First Page Looking for Forms 
          br.select_form(nr=1)
          
          # Executes Query with Given Word
          br.form['search_query'] = 'cats'
          br.submit()
           
          # Finds all links the page
          search_links = [l for l in br.links()]
          
          linkcounter = 0   

          for link in search_links:
              linkcounter  += linkcounter

          # Selects By Upload Rate (it's a hack now needs to be context independent)         
          br.follow_link(search_links[15])
          html = br.response().read()
          soup = BeautifulSoup(html)
          soup.prettify()
          
          # Creates Video Dictionary For Results
          search_results = soup.findAll('div', attrs={'class': 'result-item *sr '})
          
          videoData = {} 
          counter_vids = 0
          
          for result in search_results:
              
              counter_vids = counter_vids + 1
              
              # Gets Elements Within Result              
              links = result.findAll('a')
              images = result.findAll('img', attrs = {'alt' : 'Thumbnail'})
              added = result.find('span', attrs = {'class' : 'date-added'}).find(text=True)
              viewcount = result.find('span', attrs = {'class' : 'viewcount'}).find(text=True)              
              
              for image in images:
                  thumb = "http:"+image['src']
              
              # builds dict with result
              videoData[counter_vids] = { "thumb" : thumb, "dateadded" : added, "viewcount" : viewcount, "link" : "http://www.youtube.com/" + str(links[0]['href'])} # stores in dict
              
          finalResult = simplejson.dumps(videoData)
          
          print ''
          print finalResult
          
                  
############################################ Handlers  ###################################################

def main():
    application = webapp.WSGIApplication([('/tasks/store_videos', StoreVideos),
                                          ('/tasks/monitor_videos', MonitorVideos),
                                          ('/tasks/scrape_page', ScrapePage),
                                          ('/', MainHandler),
                                          ('/output/display_videos', DisplayVideos)],
                                         debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
